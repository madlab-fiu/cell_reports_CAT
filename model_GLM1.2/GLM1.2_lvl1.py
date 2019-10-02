#!/usr/bin/env python

"""
===============================================================
wmaze_fMRI: Mandy Thesis -- Fixed before Conditional -- Model 6
===============================================================
First level workflow for UM GE 750 wmaze task data

- WMAZE Model 6 Version 1.3.2
  - Use FSL ROI to recreate EPI data, removing last 3 volumes
  - Removed last 3 trials before EV creation
  - EV directory (Model 6) --- /home/data/madlab/data/mri/wmaze/scanner_behav/WMAZE_001/MRthesis/model6


- python wmaze_lvl1.py -s WMAZE_001
                       -o /home/data/madlab/data/mri/wmaze/frstlvl/wmaze_MRthesis/fixed_before_conditional/model6
                       -w /home/data/madlab/scripts/wmaze/anal_MR_thesis/fixed_before_conditional/model6/status/lvl1

Note: DOF file is writing out in numpy hexadecimal format
      Example: 0x1.64p+7 
      print((1 + 6./0x10 + 4./0x100) * 2**7) = 178
"""

import os
from nipype.pipeline.engine import Workflow, Node, MapNode
from nipype.interfaces.utility import IdentityInterface, Function, Merge 
from nipype.interfaces.io import DataGrabber, DataSink
from nipype.algorithms.modelgen import SpecifyModel
from nipype.interfaces.fsl.model import Level1Design, FEATModel, FILMGLS, ContrastMgr 
from nipype.interfaces.fsl.utils import ImageMaths, ExtractROI 

###################
#### Functions ####
###################

# Grab the first dimension of an array/matrix
pop_lambda = lambda x : x[0]

def subjectinfo(subject_id):
    import os
    from nipype.interfaces.base import Bunch
    from copy import deepcopy
    import numpy as np
    base_proj_dir = '/home/data/madlab/data/mri/wmaze/scanner_behav'
    # Empty array to contain info from each run (index 1-6)
    output = []

    # For the current run, of which there are 6
    for curr_run in range(1,7):
        names = []
        onsets = []
        durations = []
        amplitudes = []
 
        data_all_before_B_corr = np.genfromtxt(base_proj_dir + '/{0}/model_GLM1.2/run{1}_all_before_B_corr.txt'.format(subject_id,curr_run),dtype = str)
        data_all_before_B_incorr = np.genfromtxt(base_proj_dir +'/{0}/model_GLM1.2/run{1}_all_before_B_incorr.txt'.format(subject_id,curr_run),dtype = str) 
        data_all_remaining = np.genfromtxt(base_proj_dir +'/{0}/model_GLM1.2/run{1}_all_remaining.txt'.format(subject_id,curr_run),dtype = str)

      
        sequence = ['all_before_B']
        for curr_type in sequence:
            corr_array_name = eval('data_{0}_corr'.format(curr_type))
            incorr_array_name = eval('data_{0}_incorr'.format(curr_type))
            if incorr_array_name.size > 0: #MORE THAN ONE MISTAKE MADE 
                curr_names = ['{0}_corr'.format(curr_type), '{0}_incorr'.format(curr_type)]
                curr_corr_onsets = map(float, corr_array_name[:,0])
                curr_corr_durations = map(float, corr_array_name[:,1])
                curr_corr_amplitudes = map(float, corr_array_name[:,2])
                if incorr_array_name.size == 3: #ONLY ONE ERROR 
                    curr_incorr_onsets = [float(incorr_array_name[0])]
                    curr_incorr_durations = [float(incorr_array_name[1])]
                    curr_incorr_amplitudes = [float(incorr_array_name[2])]
                else: #MORE THAN ONE ERROR
                    curr_incorr_onsets = map(float, incorr_array_name[:,0])
                    curr_incorr_durations = map(float, incorr_array_name[:,1])
                    curr_incorr_amplitudes = map(float,incorr_array_name[:,2]) 
                curr_onsets = [curr_corr_onsets, curr_incorr_onsets]
                curr_durations = [curr_corr_durations, curr_incorr_durations]
                curr_amplitudes = [curr_corr_amplitudes, curr_incorr_amplitudes]
            else: #NO MISTAKES WERE MADE
                curr_names = ['{0}_corr'.format(curr_type)]
                curr_corr_onsets = map(float, corr_array_name[:,0])
                curr_corr_durations = map(float, corr_array_name[:,1])
                curr_corr_amplitudes = map(float, corr_array_name[:,2])
                curr_onsets = [curr_corr_onsets]
                curr_durations = [curr_corr_durations]
                curr_amplitudes = [curr_corr_amplitudes]             
            names.append(curr_names) 
            onsets.append(curr_onsets)
            durations.append(curr_durations)
            amplitudes.append(curr_amplitudes)
  
        ## ALL REMAINING TRIALS ## 
        curr_names = ['all_remaining']
        curr_corr_onsets = map(float, data_all_remaining[:,0])
        curr_corr_durations = map(float, data_all_remaining[:,1])
        curr_corr_amplitudes = map(float, data_all_remaining[:,2])
        curr_onsets = [curr_corr_onsets]
        curr_durations = [curr_corr_durations]
        curr_amplitudes = [curr_corr_amplitudes]         
        names.append(curr_names)  
        onsets.append(curr_onsets)
        durations.append(curr_durations)
        amplitudes.append(curr_amplitudes)        
        

        # If any element in names is a list instead of a single value, for those elements
        if any(isinstance(el, list) for el in names):
            names = [el for sublist in names for el in sublist]  
        if any(isinstance(el, list) for el in onsets):
            onsets = [el_o for sublist_o in onsets for el_o in sublist_o]
        if any(isinstance(el, list) for el in durations):
            durations = [el_d for sublist_d in durations for el_d in sublist_d]
        if any(isinstance(el, list) for el in amplitudes):
            amplitudes = [el_a for sublist_a in amplitudes for el_a in sublist_a]
 
        output.insert(curr_run,
                      Bunch(conditions = names,
                            onsets = deepcopy(onsets),
                            durations = deepcopy(durations),
                            amplitudes = deepcopy(amplitudes),
                            tmod = None,
                            pmod = None,
                            regressor_names = None,
                            regressors = None))
    return output

# Function to obtain and create contrasts *flexibly* in case there are not enough incorrect trials
def get_contrasts(subject_id, info):
    contrasts = []
    # For each bunch received from subjectinfo function in get_contrasts node
    for i, j in enumerate(info):
        curr_run_contrasts = []
        # Create the contrast for "ALLvsBaseline" using a t-test, j.conditions (the names received from the Bunch),
        # j.conditions is used to determine the contrast dimensions 
        cont_all = ['AllVsBase', 'T', j.conditions, [1. / len(j.conditions)] * len(j.conditions)]
        curr_run_contrasts.append(cont_all)
        # For each EV list name received from the bunch
        for curr_cond in j.conditions:
            curr_cont = [curr_cond, 'T', [curr_cond], [1]]
            curr_run_contrasts.append(curr_cont)    
      # If there exists trials in both B_after_A_corr and B_after_A_incorr    
        if 'all_before_B_corr' in j.conditions and 'all_before_B_incorr' in j.conditions:
            cont_all_corr_vs_all_incorr = ['all_corr_minus_all_incorr', 'T', ['all_before_B_corr','all_before_B_incorr'], [1, -1]]
            cont_all_incorr_vs_all_corr = ['all_incorr_minus_all_corr', 'T', ['all_before_B_corr','all_before_B_incorr'], [-1, 1]]
            curr_run_contrasts.append(cont_all_corr_vs_all_incorr)
            curr_run_contrasts.append(cont_all_incorr_vs_all_corr)
        contrasts.append(curr_run_contrasts)
    return contrasts                                                                           

# Function for naming the output types
def get_subs(cons):
    subs = []
    # For each run
    for run_cons in cons:
        run_subs = []
        # For each contrast in the run
        for i, con in enumerate(run_cons):
            # Append a tuple containing "cope#" and "cope#+name" 
            run_subs.append(('cope%d.'%(i + 1), 'cope%02d_%s.'%(i + 1, con[0])))
            run_subs.append(('varcope%d.'%(i + 1), 'varcope%02d_%s.'%(i + 1, con[0])))
            run_subs.append(('zstat%d.'%(i + 1), 'zstat%02d_%s.'%(i + 1, con[0])))
            run_subs.append(('tstat%d.'%(i + 1), 'tstat%02d_%s.'%(i + 1, con[0])))
        subs.append(run_subs)        
    return subs


# Function for extracting the motion parameters from the noise files
def motion_noise(subjinfo, files):
    import numpy as np
    motion_noise_params = []
    motion_noi_par_names = []
    # If each instance of files is not a list, make it one
    if not isinstance(files, list):
        files = [files]
    # If each instance of subjinfo is not a list, make it one
    if not isinstance(subjinfo, list):
        subjinfo = [subjinfo]
    # For each instance of files
    for j,i in enumerate(files):
        curr_mot_noi_par_names = ['Pitch (rad)', 'Roll (rad)', 'Yaw (rad)', 'Tx (mm)', 'Ty (mm)', 'Tz (mm)',
                                  'Pitch_1d', 'Roll_1d', 'Yaw_1d', 'Tx_1d', 'Ty_1d', 'Tz_1d',
                                  'Norm (mm)', 'LG_1stOrd', 'LG_2ndOrd', 'LG_3rdOrd', 'LG_4thOrd']
        # Numpy array of each motion noise files
        a_orig = np.genfromtxt(i)
        a = a_orig[:-3]
        motion_noise_params.append([[]] * a.shape[1])
        # If there are more than 17 motion noise parameters
        if a.shape[1] > 17:
            # For those additional noise parameters over 17
            for num_out in range(a.shape[1] - 17):
                # Give it a name
                out_name = 'out_{0}'.format(num_out + 1)
                curr_mot_noi_par_names.append(out_name)
        # For each instance in the second column of a
        for z in range(a.shape[1]):
            motion_noise_params[j][z] = a[:, z].tolist()
        motion_noi_par_names.append(curr_mot_noi_par_names)
    # For each instace of subjinfo    
    for j,i in enumerate(subjinfo):
        # If there are are no regressor names
        if i.regressor_names == None: 
            i.regressor_names = []
        # If there are no regressors
        if i.regressors == None: 
            i.regressors = []
        # For each instance of motion_noise_params in the current iteration of subjinfo
        for j3, i3 in enumerate(motion_noise_params[j]):
            i.regressor_names.append(motion_noi_par_names[j][j3])
            i.regressors.append(i3)          
    return subjinfo

###################################
## Function for 1st lvl analysis ##
###################################


def firstlevel_wf(subject_id,
                  sink_directory,
                  name = 'wmaze_frstlvl_wf'):
    # Create the frstlvl workflow
    frstlvl_wf = Workflow(name = 'frstlvl_wf')
    
    
    # Dictionary holding the wildcard used in datasource
    info = dict(task_mri_files = [['subject_id', 'wmaze']],
                motion_noise_files = [['subject_id']])


    # Calls the subjectinfo function with the name, onset, duration, and amplitude info 
    subject_info = Node(Function(input_names = ['subject_id'],
                                 output_names = ['output'],
                                 function = subjectinfo),
                        name = 'subject_info')
    subject_info.inputs.ignore_exception = False
    subject_info.inputs.subject_id = subject_id


    # Create another Function node to define the contrasts for the experiment
    getcontrasts = Node(Function(input_names = ['subject_id', 'info'],
                                 output_names = ['contrasts'],
                                 # Calls the function 'get_contrasts'
                                 function = get_contrasts),
                        name = 'getcontrasts')
    getcontrasts.inputs.ignore_exception = False
    # Receives subject_id as input
    getcontrasts.inputs.subject_id = subject_id
    frstlvl_wf.connect(subject_info, 'output', getcontrasts, 'info')

    
    #### subject_info (output) ----> getcontrasts (info)


    # Create a Function node to substitute names of folders and files created during pipeline
    getsubs = Node(Function(input_names = ['cons'],
                            output_names = ['subs'],
                            # Calls the function 'get_subs'
                            function = get_subs),
                   name = 'getsubs')
    getsubs.inputs.ignore_exception = False
    # Receives subject_id as input
    getsubs.inputs.subject_id = subject_id
    frstlvl_wf.connect(subject_info, 'output', getsubs, 'info')
    frstlvl_wf.connect(getcontrasts, 'contrasts', getsubs, 'cons')
    

    # Create a datasource node to get the task_mri and motion-noise files
    datasource = Node(DataGrabber(infields = ['subject_id'], 
                                  outfields = info.keys()), 
                      name = 'datasource')
    # Indicates the string template to match (in this case, any that match the field template)
    datasource.inputs.template = '*'
    # Receives subject_id as an input
    datasource.inputs.subject_id = subject_id
    # Base directory to allow branching pathways
    datasource.inputs.base_directory = os.path.abspath('/home/data/madlab/data/mri/wmaze/preproc/')
    datasource.inputs.field_template = dict(task_mri_files = '%s/func/smoothed_fullspectrum/_maskfunc2*/*%s*.nii.gz',
                                            # Filter regressor noise files
                                            motion_noise_files = '%s/noise/filter_regressor*.txt')
    # Inputs from the infields argument ('subject_id') that satisfy the template
    datasource.inputs.template_args = info
    # Forces DataGrabber to return data in sorted order when using wildcards
    datasource.inputs.sort_filelist = True
    # Do not ignore exceptions
    datasource.inputs.ignore_exception = False
    datasource.inputs.raise_on_empty = True



    # Function to remove last three volumes from functional data
                                    # Start from the first volume and end on the -3 volume
    fslroi_epi = MapNode(ExtractROI(t_min = 0, t_size = 197),
                         iterfield = ['in_file'],
                         name = 'fslroi_epi')
    fslroi_epi.output_type = 'NIFTI_GZ'
    fslroi_epi.terminal_output = 'stream'
    frstlvl_wf.connect(datasource, 'task_mri_files', fslroi_epi, 'in_file')



    # Function node to modify the motion and noise files to be single regressors
    motionnoise = Node(Function(input_names = ['subjinfo', 'files'],
                                output_names = ['subjinfo'],
                                # Calls the function 'motion_noise'
                                function = motion_noise),
                       name = 'motionnoise')
    motionnoise.inputs.ignore_exception = False
    # The bunch from subject_info function containing regressor names, onsets, durations, and amplitudes
    frstlvl_wf.connect(subject_info, 'output', motionnoise, 'subjinfo')
    frstlvl_wf.connect(datasource, 'motion_noise_files', motionnoise, 'files')



    # Makes a model specification compatible with spm/fsl designers
    # Requires subjectinfo to be received in the form of a Bunch of a list of Bunch
    specify_model = Node(SpecifyModel(), 
                         name = 'specify_model')
    # High-pass filter cutoff in seconds
    specify_model.inputs.high_pass_filter_cutoff = -1.0
    specify_model.inputs.ignore_exception = False
    # input units in either 'secs' or 'scans'
    specify_model.inputs.input_units = 'secs'
    # Time between start of one volume and the start of following volume
    specify_model.inputs.time_repetition = 2.0
    # Editted data files for model -- list of 4D files
    frstlvl_wf.connect(fslroi_epi, 'roi_file', specify_model, 'functional_runs')
    # List of event description files in 3 column format corresponding to onsets, durations, and amplitudes 
    frstlvl_wf.connect(motionnoise, 'subjinfo', specify_model, 'subject_info')

    

    # Basic interface class generates identity mappings
    modelfit_inputspec = Node(IdentityInterface(fields = ['session_info', 'interscan_interval', 
                                                          'contrasts', 'film_threshold', 
                                                          'functional_data', 'bases',
                                                          'model_serial_correlations'], 
                                                mandatory_inputs = True),
                              name = 'modelfit_inputspec')
    # Set bases to a dictionary with a second dictionary setting the value of dgamma derivatives as 'False'
    modelfit_inputspec.inputs.bases = {'dgamma':{'derivs': False}}
    # Film threshold
    modelfit_inputspec.inputs.film_threshold = 0.0
    # Interscan_interval 
    modelfit_inputspec.inputs.interscan_interval = 2.0
    # Create model serial correlations for Level1Design
    modelfit_inputspec.inputs.model_serial_correlations = True
    frstlvl_wf.connect(fslroi_epi, 'roi_file', modelfit_inputspec, 'functional_data')
    frstlvl_wf.connect(getcontrasts, 'contrasts', modelfit_inputspec, 'contrasts')
    frstlvl_wf.connect(specify_model, 'session_info', modelfit_inputspec, 'session_info')
   


    # Creates a first level SPM design matrix to demonstrate contrasts and motion/noise regressors
    level1_design = MapNode(Level1Design(),
                            iterfield = ['contrasts', 'session_info'],
                            name = 'level1_design')
    level1_design.inputs.ignore_exception = False
    # Inputs the interscan interval (in secs)
    frstlvl_wf.connect(modelfit_inputspec, 'interscan_interval', level1_design, 'interscan_interval')
    # Session specific information generated by ``modelgen.SpecifyModel``
    frstlvl_wf.connect(modelfit_inputspec, 'session_info', level1_design, 'session_info')
    # List of contrasts with each contrast being a list of the form -[('name', 'stat', [condition list], [weight list], [session list])].
    # If session list is None or not provided, all sessions are used.
    frstlvl_wf.connect(modelfit_inputspec, 'contrasts', level1_design, 'contrasts')
    # Name of basis function and options e.g., {'dgamma': {'derivs': True}}
    frstlvl_wf.connect(modelfit_inputspec, 'bases', level1_design, 'bases')
    # Option to model serial correlations using an autoregressive estimator (order 1)
    # Setting this option is only useful in the context of the fsf file
    frstlvl_wf.connect(modelfit_inputspec, 'model_serial_correlations', level1_design, 'model_serial_correlations')

    

    # Create a MapNode to generate a design.mat file for each run
    generate_model = MapNode(FEATModel(),
                             iterfield = ['fsf_file', 'ev_files'],
                             name = 'generate_model') 
    generate_model.inputs.environ = {'FSLOUTPUTTYPE': 'NIFTI_GZ'}
    generate_model.inputs.ignore_exception = False
    generate_model.inputs.output_type = 'NIFTI_GZ'
    generate_model.inputs.terminal_output = 'stream'
    # File specifying the feat design spec file 
    frstlvl_wf.connect(level1_design, 'fsf_files', generate_model, 'fsf_file')
    # Event spec files generated by level1design (condition information files)
    frstlvl_wf.connect(level1_design, 'ev_files', generate_model, 'ev_files')

    

    # Create a MapNode to estimate the model using FILMGLS -- fits the design matrix to the voxel timeseries
    estimate_model = MapNode(FILMGLS(),
                             iterfield = ['design_file', 'in_file', 'tcon_file'],
                             name = 'estimate_model')
    estimate_model.inputs.environ = {'FSLOUTPUTTYPE': 'NIFTI_GZ'}
    estimate_model.inputs.ignore_exception = False
    # Susan-smooth mask size
    estimate_model.inputs.mask_size = 5
    estimate_model.inputs.output_type = 'NIFTI_GZ'
    estimate_model.inputs.results_dir = 'results'
    # Smooth auto-correlation estimates
    estimate_model.inputs.smooth_autocorr = True
    estimate_model.inputs.terminal_output = 'stream'
    frstlvl_wf.connect(modelfit_inputspec, 'film_threshold', estimate_model, 'threshold')
    frstlvl_wf.connect(modelfit_inputspec, 'functional_data', estimate_model, 'in_file')
    # Mat file containing ascii matrix for design
    frstlvl_wf.connect(generate_model, 'design_file', estimate_model, 'design_file')
    # Contrast file containing contrast vectors
    frstlvl_wf.connect(generate_model, 'con_file', estimate_model, 'tcon_file')



    # Create a merge node to merge the contrasts - necessary for fsl 5.0.7 and greater
    merge_contrasts = MapNode(Merge(2), 
                              iterfield = ['in1'], 
                              name = 'merge_contrasts')
    frstlvl_wf.connect(estimate_model, 'zstats', merge_contrasts, 'in1')



    # Create a MapNode to transform the z2pval
    z2pval = MapNode(ImageMaths(),  
                     iterfield = ['in_file'], 
                     name='z2pval')
    z2pval.inputs.environ = {'FSLOUTPUTTYPE': 'NIFTI_GZ'}
    # Do not ignore exceptions
    z2pval.inputs.ignore_exception = False
    # Defines the operation used
    z2pval.inputs.op_string = '-ztop'
    # Set the outfile type to nii.gz
    z2pval.inputs.output_type = 'NIFTI_GZ'
    # Out-file suffix
    z2pval.inputs.suffix = '_pval'
    # Set output to stream in terminal
    z2pval.inputs.terminal_output = 'stream'
    frstlvl_wf.connect(merge_contrasts, ('out', pop_lambda), z2pval, 'in_file')



    # Create an outputspec node using IdentityInterface() to receive information from estimate_model, 
    # merge_contrasts, z2pval, generate_model, and estimate_model
    modelfit_outputspec = Node(IdentityInterface(fields = ['copes', 'varcopes', 
                                                           'dof_file', 'pfiles',
                                                           'parameter_estimates', 'zstats',
                                                           'design_image', 'design_file', 
                                                           'design_cov', 'sigmasquareds'],
                                                 mandatory_inputs = True),
                               name = 'modelfit_outputspec')
    # All lvl1 cope files
    frstlvl_wf.connect(estimate_model, 'copes', modelfit_outputspec, 'copes')
    # All lvl1 varcope files
    frstlvl_wf.connect(estimate_model, 'varcopes', modelfit_outputspec, 'varcopes')
    # All zstats across runs
    frstlvl_wf.connect(merge_contrasts, 'out', modelfit_outputspec, 'zstats')
    # 
    frstlvl_wf.connect(z2pval, 'out_file', modelfit_outputspec, 'pfiles')
    # Graphical representation of design matrix
    frstlvl_wf.connect(generate_model, 'design_image', modelfit_outputspec, 'design_image')
    # Mat file containing ascii matrix for design
    frstlvl_wf.connect(generate_model, 'design_file', modelfit_outputspec, 'design_file')
    # Graphical representation of design covariance
    frstlvl_wf.connect(generate_model, 'design_cov', modelfit_outputspec, 'design_cov')
    # Parameter estimates for each column of the design matrix
    frstlvl_wf.connect(estimate_model, 'param_estimates', modelfit_outputspec, 'parameter_estimates')
    # Degrees of freedom
    frstlvl_wf.connect(estimate_model, 'dof_file', modelfit_outputspec, 'dof_file')
    # Summary of residuals
    frstlvl_wf.connect(estimate_model, 'sigmasquareds', modelfit_outputspec, 'sigmasquareds')



    # Create a datasink node to save output from multiple points in the pipeline
    sinkd = MapNode(DataSink(),
                    iterfield = ['substitutions', 'modelfit.contrasts.@copes', 'modelfit.contrasts.@varcopes',
                                 'modelfit.estimates', 'modelfit.contrasts.@zstats'],
                    name = 'sinkd')
    sinkd.inputs.base_directory = sink_directory 
    sinkd.inputs.container = subject_id
    frstlvl_wf.connect(getsubs, 'subs', sinkd, 'substitutions')
    frstlvl_wf.connect(modelfit_outputspec, 'parameter_estimates', sinkd, 'modelfit.estimates')
    frstlvl_wf.connect(modelfit_outputspec, 'sigmasquareds', sinkd, 'modelfit.estimates.@sigsq')
    frstlvl_wf.connect(modelfit_outputspec, 'dof_file', sinkd, 'modelfit.dofs')
    frstlvl_wf.connect(modelfit_outputspec, 'copes', sinkd, 'modelfit.contrasts.@copes')
    frstlvl_wf.connect(modelfit_outputspec, 'varcopes', sinkd, 'modelfit.contrasts.@varcopes')
    frstlvl_wf.connect(modelfit_outputspec, 'zstats', sinkd, 'modelfit.contrasts.@zstats')
    frstlvl_wf.connect(modelfit_outputspec, 'design_image', sinkd, 'modelfit.design')
    frstlvl_wf.connect(modelfit_outputspec, 'design_cov', sinkd, 'modelfit.design.@cov')
    frstlvl_wf.connect(modelfit_outputspec, 'design_file', sinkd, 'modelfit.design.@matrix')
    frstlvl_wf.connect(modelfit_outputspec, 'pfiles', sinkd, 'modelfit.contrasts.@pstats')

    return frstlvl_wf



###############################
## Creates the full workflow ##
###############################

def create_frstlvl_workflow(args, name = 'wmaze_MR_frstlvl'):
    # Creates a dictionary containing variables subject_id, sink_directory, and name
    kwargs = dict(subject_id = args.subject_id,
                  sink_directory = os.path.abspath(args.out_dir),
                  name = name)
    # Passes the value of all dictionary items to firstlevel_wf
    frstlvl_workflow = firstlevel_wf(**kwargs)
    # Returns all those values
    return frstlvl_workflow

# If the thread is the primary thread
if __name__ == "__main__":
    # Import ArgumentParser from python
    from argparse import ArgumentParser
    # Variable containing the ArgumentParser class information for this particular script
    parser = ArgumentParser(description = __doc__)
    # Add argument for subject_id when you flag "-s"
    parser.add_argument("-s", "--subject_id", dest = "subject_id",
                        help = "Current subject id", required = True)
    # Add argument for output directory when you flag "-o"
    parser.add_argument("-o", "--output_dir", dest = "out_dir",
                        help = "Output directory base")
    # Add argument for working directory when you flag "-w"
    parser.add_argument("-w", "--work_dir", dest = "work_dir",
                        help = "Working directory base")
    # Parser arguments are passed to the create_frstlvl_workflow function
    args = parser.parse_args()

    # Object containing all important workflow info
    wf = create_frstlvl_workflow(args)

    # If not None, then assume a working directory
    if args.work_dir:
        work_dir = os.path.abspath(args.work_dir)
    # If not valid working dir, make the current dir the work_dir    
    else:
        work_dir = os.getcwd()

    wf.config['execution']['crashdump_dir'] = '/scratch/madlab/crash/mandy_crash/model_GLM1.2/lvl1'
    wf.base_dir = work_dir + '/' + args.subject_id
    wf.run(plugin='SLURM', plugin_args={'sbatch_args': ('-p investor --qos pq_madlab -N 1 -n 1'), 'overwrite': True})

