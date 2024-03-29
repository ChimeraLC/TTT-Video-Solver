import cv2
import numpy as np
import copy
import tensorflow as tf
import time
from TTTSolver import *
"""
Converts an approximated contour into a 
counterclockwise (starting from top left) grid of 4 points
"""
def FlattenSort(approx):
	flattened = approx.ravel()
	# Finding counterclockwise orientation
	grid = [[flattened[0], flattened[1]], 
		[flattened[0], flattened[1]],
		[flattened[0], flattened[1]],
		[flattened[0], flattened[1]]]
	# Top left value
	for i in range(int(len(flattened)/2)):
		if (flattened[2*i] + flattened[2*i+1] < grid[0][0] + grid[0][1]):
			grid[0][0] = flattened[2*i]
			grid[0][1] = flattened[2*i+1]
	# Bottom right value
	for i in range(int(len(flattened)/2)):
		if (flattened[2*i] + flattened[2*i+1] > grid[2][0] + grid[2][1]):
			grid[2][0] = flattened[2*i]
			grid[2][1] = flattened[2*i+1]

	# Bottom Left value
	for i in range(int(len(flattened)/2)):
		if (flattened[2*i] - flattened[2*i+1] < grid[1][0] - grid[1][1]):
			grid[1][0] = flattened[2*i]
			grid[1][1] = flattened[2*i+1]

			
	# Top right value
	for i in range(int(len(flattened)/2)):
		if (flattened[2*i] - flattened[2*i+1] > grid[3][0] - grid[3][1]):
			grid[3][0] = flattened[2*i]
			grid[3][1] = flattened[2*i+1]
	
	return np.array(grid, dtype = "float32")

"""
Converts a contour approx into a larger image the shape of frame
color indicates if the frame is colored or not
"""
def Resize(frame, approx, color = False):
	# Get frame shape
	if (color):
		y, x, _ = frame.shape
	else:
		y, x = frame.shape

	# Get corresponding points
	warpGrid = np.array([[10, 10], [10, y-10], [x-10, y-10], [x-10, 10]], dtype="float32")
	grid = FlattenSort(approx)

	warpMethod = cv2.getPerspectiveTransform(grid, warpGrid)
	warped = cv2.warpPerspective(frame, warpMethod, (x+10, y+10))
	return warped

"""
Finds the top left point of the contour approx
"""
def TopLeft(approx):
	# Flatten the contour
	flattened = approx.ravel()
	ret = [flattened[0], flattened[1]]
	# Find the point whose coordinates have the least sum
	for i in range(int(len(flattened)/2)):
		if (flattened[2*i] + flattened[2*i+1] < ret[0] + ret[1]):
			ret[0] = flattened[2*i]
			ret[1] = flattened[2*i+1]
	return ret

"""
Beginning of main program
"""
#Load tensorflow model
model = tf.keras.Sequential([
    tf.keras.layers.Flatten(input_shape=(20, 30)),
    tf.keras.layers.Dense(128, activation='relu'),
    tf.keras.layers.Dense(2)
])
model.compile(optimizer='adam',
              loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
              metrics=['accuracy'])
model.load_weights('./Checkpoints/TTT_Checkpoint').expect_partial()

# Initialize the webcam
cap = cv2.VideoCapture(0)

# Initial variables
found = False
savedPosition = -1
lastTime = 0

while True:
	# Read each frame from the webcam
	_, frame = cap.read()

	y, x, c = frame.shape

	total_area = x * y

	# Current frame time
	currentTime = time.time()

	# Flip the frame vertically
	frame = cv2.flip(frame, 1)
	blur = cv2.blur(frame, (3, 3))
	frame2 = cv2.cvtColor(blur, cv2.COLOR_BGR2GRAY)
	
	# Apply a threshold
	thresh = cv2.adaptiveThreshold(
		   frame2, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 51, 3
	)

	# Find contours
	contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
	
	# Find the largest contour thats not too large
	maxArea = 0
	for c in contours:
        # Approximate the contour
		peri = cv2.arcLength(c, True)
		approx = cv2.approxPolyDP(c, 0.01 * peri, True)

		area = cv2.contourArea(c)
        # Check for contours that are quadrilateral and also not too small
		if area > maxArea and area / total_area < 0.9 and len(approx) == 4:
			maxArea = area
			# Save the contour elements
			originalContour = approx

	# Map the shape onto a rectangle
	warped = Resize(thresh, originalContour)
	warpedColor = Resize(frame, originalContour, True)

	# fixing broken lines and thicken shapes
	kernel = np.ones((3, 3), np.uint8) 
	d_im = cv2.dilate(warped, kernel, iterations=1)
	e_im = cv2.erode(d_im, kernel, iterations=1) 
	warped2 = e_im
	inner_contours, _ = cv2.findContours(warped2, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
	for i in inner_contours:
		cv2.drawContours(warped2, [i], -1, (0, 0, 0), 10)

	# Locate and count contours
	inner_contours, _ = cv2.findContours(warped2, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
	x1, y1 = warped2.shape
	outerArea = x1*y1

	# Used to save images and coorginates
	squares = []
	originals = []

	for i in inner_contours:
		peri = cv2.arcLength(i, True)
		approx = cv2.approxPolyDP(i, 0.02 * peri, True)
		
		innerArea = cv2.contourArea(approx)
		if (innerArea/outerArea > 0.02 and innerArea/outerArea < 0.2 and len(approx) < 7):
			# Confirming its somewhat square shaped
			_, _, w,h = cv2.boundingRect(approx)
			if (w/h < 0.5 or h/w < 0.5 or w * h / x1 / y1 > 0.5):
				continue
			cv2.drawContours(warped, [approx], 0, (255, 255, 0), 3)
			cv2.drawContours(warpedColor, [approx], 0, (255, 255, 0), 3)
			# TODO: order the squares
			squares.append(Resize(warped, approx))
			originals.append(approx)
			# Time since found
			lastTime = time.time()

	# If the found contour has specifically 9 inner squares
	if (len(squares) == 9):
		# Making copies of the contours for continued use
		savedSquares = squares
		savedOriginals = copy.deepcopy(originals)
		originalPoints = []
		for i in range(9):
			originalPoints.append(TopLeft(originals[i]))
		savedOriginalContour = originalContour
		saved = warpedColor

		# Calculate how large the image is and compensate
		
		imageRatio = maxArea / 10000

		# Sort the elements to be top left to bottom right
		
		# sorting by rows
		sort = sorted(zip(originalPoints, savedSquares, savedOriginals), key=lambda x: x[0][1])
		originalPoints = [x for x, _, _ in sort]
		savedOriginals = [x for _, _, x in sort]
		savedSquares = [x for _, x, _ in sort]

		# sort the columns
		for i in range(3):
			sort = sorted(zip(originalPoints[i*3:i*3+3], savedSquares[i*3:i*3+3],
		     savedOriginals[i*3:i*3+3]), key=lambda x: x[0][0])
			originalPoints[i*3:i*3+3] = [x for x, _ ,_ in sort]
			savedOriginals[i*3:i*3+3] = [x for _, _ ,x in sort]
			savedSquares[i*3:i*3+3] = [x for _, x, _ in sort]

		# Shrink images for use with model				
		alteredSquares = []

		# Alter images
		for i in range(9):
			res = cv2.resize(savedSquares[i], dsize=(33, 25), interpolation=cv2.INTER_CUBIC)
			alteredSquares.append(cv2.getRectSubPix(res, (30, 20), (17, 13)))

		# Reading grid
		predictions = model.predict(np.array(alteredSquares), verbose=0)
		predictions = [np.argmax(x) for x in predictions]
		# Checking for any white squares
		for i in range(9):
			if (np.mean(alteredSquares[i]) > 250):
				predictions[i] = 2

		# Solve for best next move
		position, player = Solve(predictions)
		# Save the position if its valid
		if (position != -1):
			savedPosition = position

			#Indicate that a valid next move has been found
			found = True

	# If theres a valid 3x3 square, solve and display if hasn't been too long
	if found and currentTime - lastTime < 0.5:
		# Find center of corresponding square
		currentContour = savedOriginals[savedPosition]
		flattened = FlattenSort(currentContour)
		cx = 0
		cy = 0
		for i in range(len(flattened)):
			cx += flattened[i][0]
			cy += flattened[i][1]

		cx = int(cx / len(flattened))
		cy = int(cy / len(flattened))
			# Map positions onto the original image
		mapGrid = FlattenSort(savedOriginalContour)
		y, x = warped2.shape
		warpGrid = np.array([[0, 0], [0, y], [x, y], [x, 0]], dtype="float32")

		h, mask = cv2.findHomography(warpGrid, mapGrid)
		pts = np.array([cx, cy], np.float32)
		pts1 = pts.reshape(-1,1,2).astype(np.float32)
		dst1 = cv2.perspectiveTransform(pts1, h)

		# Draw text onto image
		cv2.putText(frame, (["o", "x"])[player], 
	      (int(dst1[0][0][0]) - int(10 * imageRatio),
		  int(dst1[0][0][1]) + int(10 * imageRatio)),
		  cv2.FONT_HERSHEY_SIMPLEX, 1 * imageRatio, (0, 0, 0), 
		  max(2, int(2 * imageRatio)))
		
	# Show final output
	cv2.imshow("Output", frame) 
	if cv2.waitKey(1) == ord('q'):
		break

# release the webcam and destroy all active windows
cap.release()

cv2.destroyAllWindows()


