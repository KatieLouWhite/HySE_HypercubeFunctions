"""

Functions that help finding the frames of interest to calculate the hypercube from the raw data


"""


import numpy as np
import cv2
import os
from datetime import datetime
from scipy.signal import savgol_filter, find_peaks
import matplotlib
from matplotlib import pyplot as plt
import imageio
# import matplotlib.colors as colors
# import matplotlib.cm as cmx
from mpl_toolkits.axes_grid1 import make_axes_locatable
matplotlib.rcParams.update({'font.size': 14})
plt.rcParams["font.family"] = "arial"


import HySE_ImportData
import HySE_UserTools




def FindHypercube(DataPath, Wavelengths_list, **kwargs):
	info="""
	Input: 
	
	- DataPath: Path to the data
	
	- kwargs: Parameters for the smoothing of the data (savgol filter) and finding peaks
			  Sets to default numbers that typically give decent results if nothing is input
				- Help = True: to print this help message')
				- Blind = False: Ignores automatic edge detection if sets to true, and only uses 
						expected plateau/dark sizes to find the frames for each wavelength.
						To use when the data is too noisy to clearly see edges (~brute force method)
						Expects: PlateauSize,
						         StartFrame
				- PlotGradient = True: To plot gratient of smoothed trace and detected peaks')
					To see effect of other parameters when optimising')
				- PrintPeaks = True: To print the list of all detected peaks and their positions')
				- MaxPlateauSize = Integer: Set the maximal expected size for a plateau.')
				- WindowLength = Integer: Window over which the smoothing of the trace is performed')
						If the data consists of NxRGB cycles, this number should be a factor of 3')
				- PolyOrder = Integer: Order of the polynomial used in smoothing (Savitzky-Golay)')
				- PeakHeight = Float: Detection threshold applied to the gradient of the smoothed trace')
						to find edges between neighbouring colours')
				- PeakDistance = Integer: Minimal distance between neightbouring peaks/plateaux')
						Depends on the repeat number, and will impact the detection of double plateaux')
				- DarkMin = Integer: Set the minimal size of the long dark between succesive sweeps')
						Depends on the repeat numbner, and will impact the detection of individial sweeps')
				- PlateauSize = Integer: Set the expected average size for a plateau (in frame number)')
						Depends on the repeat number and will impact how well double plateaux are handled')
						Automatically adjusts expected size when plateaux are detected, but needs to be set')
						manually if a full sweep could not be detected automatically.')
				- StartFrame = Integer: Indicates where the sweep begins, when using the blind method
				- CropImDimensions = [xmin, xmax, ymin, ymax]: coordinates of image crop (default Full HD)')
				- ReturnPeaks = True: if want the list of peaks and peak distances')
						(for manual tests, for example if fewer than 8 colours')
				- Ncolours = integer: if different from 8 (for example, if one FSK was off)')
				- fps = integer (frame per second)
				- SaveFig = True: Whether to save figure
				
	Output:
	
	- EdgePos: Positions indicating where each sections of frames is for each wavelength 
			   for all sweeps in the dataset
	
	
	"""

		## Check if the user wants to return the peaks
	try:
		ReturnPeaks = kwargs['ReturnPeaks']
		print(f'ATTENTION: ReturnPeaks is set to True. Be careful, the output will have three elements!')
	except KeyError:
		ReturnPeaks = False

	## Check if user wants list of optional parameters
	try:
		Help = kwargs['Help']
	except KeyError:
		Help = False
	if Help:
		print(info)
		if ReturnPeaks:
			return 0,0,0
		else:
			return 0
	else:
		print(f'Add \'Help=True\' in input for a list and description of all optional parameters ')
	
	## Check if user wants to plot the gradient (to optimise parameters)
	try:
		PlotGradient = kwargs['PlotGradient']
	except KeyError:
		PlotGradient = False

	## Check if SaveFig
	try:
		SaveFig = kwargs['SaveFig']
	except KeyError:
		SaveFig = True
		
	## Check if user wants to print the list of peaks and distances 
	## between them (to optimise parameters)
	try:
		PrintPeaks = kwargs['PrintPeaks']
	except KeyError:
		PrintPeaks = False

	## Check if user is setting fps
	try:
		fps = kwargs['fps']
	except KeyError:
		fps = 60*3
		
	## Check if user has set the max plateau size
	## Used to handle double plateaux when neighbouring wavelengths
	## give too low contrast 
	## Needs to be adjusted if chaning repeat number
	try:
		MaxPlateauSize = kwargs['MaxPlateauSize']
		print(f'Max plateau size set to {MaxPlateauSize}')
	except KeyError:
		MaxPlateauSize = 40
		print(f'Max plateau size set to default of {MaxPlateauSize}')
	  
	## Check if user has set the minimum size of long dark (separating sweeps)
	## Will vary with repeat number, should be larger than MaxPlateauSize
	try:
		DarkMin = kwargs['DarkMin']
		print(f'Min long dark size set to {DarkMin}')
	except KeyError:
		DarkMin = 90
		print(f'Min long dark size set to default of {DarkMin}')
		
	## Check if the user has input the expected plateau size
	try:
		PlateauSize = kwargs['PlateauSize']
		print(f'Expected plateau size set to {PlateauSize}')
	except KeyError:
		PlateauSize = 45
		print(f'Expected plateau size set to default {PlateauSize}')

	## Check if the user wants to return the peaks
	try:
		Ncolours = kwargs['Ncolours']
		print(f'Assuming {Ncolours} wavelengths instead of normal 8')
	except KeyError:
		Ncolours = 8

	## Check if Blind
	try:
		Blind = kwargs['Blind']
	except KeyError:
		Blind = False

	
	## Import trace

	## If CropImDimensions dimensions have been specified, pass on to import data function
	try:
		CropImDimensions = kwargs['CropImDimensions']
		trace = HySE_ImportData.ImportData(DataPath,Trace=True, CropImDimensions=CropImDimensions)
	except KeyError: 
		trace = HySE_ImportData.ImportData(DataPath,Trace=True)

	## Find peaks
	peaks, SGfilter, SGfilter_grad = FindPeaks(trace, **kwargs)
	## Find distance between peaks
	peaks_dist = GetPeakDist(peaks, 0, len(trace))
	if PrintPeaks:
		print(peaks_dist) 

	if Blind:
		try:
			StartFrame = kwargs['StartFrame']
		except KeyError:
			StartFrame = 0
			print(f'Using the blind method. Set StartFrame to indicate where the sweep begins')
		
		EdgePos = []
		for i in range(0,2*Ncolours+1): ## 0 to 16 + dark
			EdgePos.append([int(StartFrame+PlateauSize*(i+1)), int(PlateauSize)])
		EdgePos=np.array([EdgePos])

		print(EdgePos)

	else:
		## Find sweep positions, will print edges for each identified sweep
		EdgePos, Stats = GetEdgesPos(peaks_dist, DarkMin, 0, len(trace), MaxPlateauSize, PlateauSize, Ncolours, printInfo=True)
	
	## Now make figure to make sure all is right
	SweepColors = ['royalblue', 'indianred', 'limegreen', 'gold', 'darkturquoise', 'magenta', 'orangered', 'cyan', 'lime', 'hotpink']
	fs = 9
	
	fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(13,5))
	ax.plot(trace, '.-', color='gray', label='Dazzle - White')
	ax.plot(SGfilter, '-', color='black', label='Savitzky-Golay filter')
	
	if PlotGradient: ## For debugging
		## Plot gradient
		ax2=ax.twinx()
		ax2.plot(SGfilter_grad, '-', color='limegreen', label='Gradient')
		## Plot peaks
		for i in range(0,len(peaks)):
			if i==0:
				ax.axvline(peaks[i], ls='dotted', c='red', label='Plateau edge')
			else:
				ax.axvline(peaks[i], ls='dotted', c='red')
		ax2.set_ylabel('Gradient', c='limegreen', fontsize=16)
		ax2.yaxis.label.set_color('limegreen')
		
		
	for k in range(0,len(EdgePos)):
		edges = EdgePos[k]
		for i in range(0,len(edges)):
			s, ll = edges[i,0], edges[i,1]
			ax.axvline(s, ls='dashed', c=SweepColors[k])
			if i<8:
				RGB = HySE_UserTools.wavelength_to_rgb(Wavelengths_list[i])
				ax.text(s+7, SGfilter[s+10]+3, Wavelengths_list[i], fontsize=fs, c=RGB)
			elif (i==8):
				ax.text(s, SGfilter[s+10]-3, 'DARK', fontsize=fs, c='black')
			else:
				RGB = HySE_UserTools.wavelength_to_rgb(Wavelengths_list[i-1])
				ax.text(s+8, SGfilter[s+10]+3, np.round(Wavelengths_list[i-1],0), fontsize=fs, c=RGB)

	# ax.legend()
	## Add time label
	ax.set_xlabel('Frame', fontsize=16)
	ax3 = ax.twiny()
	ax3.set_xlim(ax.get_xlim())
	NN = len(trace)
	Nticks = 10
	# new_tick_locations = np.array([NN/5, 2*NN/5, 3*NN/5, 4*NN/5, NN-1])
	new_tick_locations = np.array([k*NN/Nticks for k in range(0,Nticks+1)])
	def tick_function(x):
		V = x/fps
		return ["%.0f" % z for z in V]

	ax3.set_xticks(new_tick_locations)
	ax3.set_xticklabels(tick_function(new_tick_locations))

	ax3.set_xlabel('Time [s]', fontsize=16)

	ax.set_ylabel('Average image intensity', fontsize=16)

	ax.set_title('Trace and Detected Sweeps', fontsize=20)
	plt.tight_layout()
	
	## Find current path and time to save figure
	cwd = os.getcwd()
	time_now = datetime.now().strftime("%Y%m%d__%I-%M-%S-%p")
	day_now = datetime.now().strftime("%Y%m%d")
	

	Name_withExtension = DataPath.split('/')[-1]
	Name = Name_withExtension.split('.')[0]
	Path = DataPath.replace(Name_withExtension, '')

	if SaveFig:
		PathToSave = f'{Path}{time_now}_{Name}_Trace.png'
		# plt.savefig(f'{cwd}/{time_now}_Trace.png')
		print(f'Saving figure at this location: \n   {PathToSave }')
		plt.savefig(PathToSave)
	plt.show()

	if ReturnPeaks:
		return EdgePos, peaks, peaks_dist
	
	else:
		return EdgePos







def FindPeaks(trace, **kwargs):
	"""
	Input: 
	
	- trace of the data (1D)
	
	- kwargs: Parameters for the smoothing of the data (savgol filter) and finding peaks
			  Sets to default numbers that typically give decent results if nothing is input
			  
			  Expects:
				window_length = integer (factor 3)
				polyorder = interger (<window_length)
				peak_height = float
				peak_distance = integer
				PlotGradient = True/False
				
	Output:
	
	- peaks
	
	- SGfilter (for plotting)
	
	
	"""
	## Check if smoothing Window Length set by user
	try:
		window_length = kwargs['WindowLength']
		## Make sure that the value is a factor of 3, if not warn user that results won't be as good
		if window_length%3!=0:
			print(f'Window length {window_length} is not a factor of 3')
			print(f'Input a factor of 3 unless you are sure that the repeat number is no longer x3 RGB frames')
		## If not, set default value
	except KeyError:
		print(f'No window length or polyorder input. Setting to 6, 1')
		window_length = 6
	
	## Check if smoothing polyorder set by user
	try:
		polyorder = kwargs['PolyOrder']
	except KeyError:
		polyorder = 1
		
	## Check if peak height set by user
	try:
		peak_height = kwargs['PeakHeight']
		print(f'Setting peak height to {peak_height}')
	except KeyError:
		peak_height = 0.03
		print(f'No peak height input, setting it to default {peak_height}')
	
	## Check if peak distance set by user
	try:
		peak_distance = kwargs['PeakDistance']
		print(f'Setting peak distance to {peak_distance}')
	except KeyError:
		peak_distance = 14
		print(f'No peak distance input, setting it to default {peak_distance}')
	
	SGfilter = savgol_filter(trace, window_length, polyorder)
	SGfilter_grad = np.abs(np.gradient(SGfilter))
	
	peaks, _ = find_peaks(SGfilter_grad, height=peak_height, distance=peak_distance)
	return peaks, SGfilter, SGfilter_grad




def GetPeakDist(peaks, FrameStart, FrameEnd):
	peaks_dist = []
	for i in range(0,len(peaks)-1):
		peaks_dist.append([peaks[i], peaks[i+1]-peaks[i]])
	return np.array(peaks_dist)




def GetEdgesPos(peaks_dist, DarkMin, FrameStart, FrameEnd, MaxPlateauSize, PlateauSize, Ncolours, printInfo=True):
	"""
	Function that identify sweeps from the detected peaks.
	Input:
		- Peaks_dist: outut from GetPeakDist
		- DarkMin: Minimal size for a long dark marking transition between successive sweeps
		- FrameStart: (No longer used) Allows to only consider a subsection of the dataset
					starting after FrameStart instead of 0
		- FrameEnd: (No longer used) Allows to only consider a subsectino of the dataset
					ending at FrameEnd instead of -1
		- MaxPlateauSize: Maximal expected size for a normal pleateau. Helps handle double plateau that 
					occur when two neightbouring colours have poor contrast and the transition
					cannot be detected by the peak threshold.
					Should be smaller than DarkMin.
		- PleateauSize: Expected plateay size. Helps handle double plateau that 
					occur when two neightbouring colours have poor contrast and the transition
					cannot be detected by the peak threshold.
		- Ncolours: Added to handle cases when there are fewer than 8 wavelengths (one FSK off for example)
		- PrintInfo: (default True): prints details about each sweep

	Output:
		- EdgePos: Array containing the coordinates for each sweep and each plateau/wavelength within each sweep.
					Used to identify appropriate frames and then compute the hypercube.
		- Stats: (No longer used) Statistics about the identified sweeps. Useful for debugging.

	"""
	EdgePos = []
	temp = []
	Stats = []
	## Expected size of a sweep (based on number of colours (8*2) + dark (1))
	# temp_size = 17
	temp_size = 17 - (8-Ncolours)
	for i in range(0,len(peaks_dist)):
		## Check if we are within the right range to avoid errors
		if (peaks_dist[i,0]>=FrameStart and peaks_dist[i,0]<=FrameEnd):
			if peaks_dist[i,1]>DarkMin: ## Long dark - new sweep
				temp = np.array(temp)
				# print(f'  Start of a new plateau. len(temp) = {len(temp)}, time_size = {temp_size}')
				if len(temp)==temp_size:
					temp_avg = np.average(temp[:,1])
					temp_std = np.std(temp[:,1])
					if printInfo:
						print(f'\n{temp[:,1]}\n  separation: {peaks_dist[i,1]} - {len(temp)} plateaux, avg {temp_avg:.2f} frames +/- {temp_std:.2f}\n')
					EdgePos.append(temp)
					PlateauSize = int(np.round(temp_avg))
					Stats.append([temp_avg, temp_std])
				temp = []
			## If at the end of the trace, check if we have a full sweep
			elif i==(len(peaks_dist)-1):
				# print(f'At the end of trace')
				if len(temp)==(temp_size-1):
					# print(f'Have full sweep')
					x0 = peaks_dist[i,0]
					temp.append([peaks_dist[i,0], PlateauSize])                    
					temp = np.array(temp)
					temp_avg = np.average(temp[:,1])
					temp_std = np.std(temp[:,1])
					if printInfo:
						print(f'{temp[:,1]}\n  separation: {peaks_dist[i,1]} - {len(temp)} plateaux, avg {temp_avg:.2f} frames +/- {temp_std:.2f}\n')
					EdgePos.append(temp)
					Stats.append([temp_avg, temp_std])    
			else:
				## Ad hoc to fix white double plateau
				## Sometimes two neighbouring colours are too similar and the code can't pick up the difference
				if peaks_dist[i, 1]>MaxPlateauSize: 
					# print(f'Double plateau:  peaks_dist[i, 1] = {peaks_dist[i, 1]}, MaxPlateauSize = {MaxPlateauSize}')
					temp.append([peaks_dist[i,0], PlateauSize])
					temp.append([peaks_dist[i,0]+PlateauSize, (peaks_dist[i, 1])])
				else:
					## In the sweep, keep appending
					# print(f'  Regular sweep, keep appending')
					temp.append([peaks_dist[i,0], peaks_dist[i, 1]])
	
	## Print error message with suggestions if no sweep found
	if len(EdgePos)==0:
		print(f'\nNo sweep found. Set PlotGradient to True and play with parameters to improve detection')
		print(f'   To adjust smoothing: window_length, polyorder')
		print(f'   To adjust edge detection: peak_height, peak_distance')
		print(f'   To adjust the number of expected wavelengths: Ncolours')
	return np.array(EdgePos), np.array(Stats)

