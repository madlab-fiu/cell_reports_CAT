#!/usr/bin/env python

"""
======================================
GLM2_fMRI: Comprehensive -- Model GLM2
======================================
First level workflow for UM GE 750 wmaze task data

- Comprehensive Model GLM2
   - Does not include fixed before conditional trials with intervening BLs
   - General linear model (not LSS)
   - Use FSL ROI to recreate EPI data, removing last 3 volumes
   - Removed last 3 trials before EV creation
     - EV directory  --- /home/data/madlab/data/mri/wmaze/GLM2/scanner_behav/WMAZE_001/model_GLM2

- python GLM2_lvl1.py -s WMAZE_001
                       -o /home/data/madlab/data/mri/GLM2/frstlvl/model_GLM2
                       -w /home/data/madlab/scripts/GLM2/model_GLM2/status/lvl1
Note: DOF file is writing out in numpy hexadecimal format
      Example: 0x1.64p+7 
      print((1 + 6./0x10 + 4./0x100) * 2**7) = 178
"""

import os
from nipype.pipeline.engine import Workflow, Node, MapNode
from nipype.interfaces.utility import IdentityInterface, Function, Merge
from nipype.utils.misc import getsource
from nipype.interfaces.io import DataGrabber, DataSink
from nipype.algorithms.modelgen import SpecifyModel
from nipype.interfaces.fsl.model import Level1Design, FEATModel, FILMGLS, ContrastMgr
from nipype.interfaces.fsl.utils import ImageMaths, ExtractROI


###################
#### Functions ####
###################


pop_lambda = lambda x : x[0] #grab the first dimension of an array/matrix

def subjectinfo(subject_id):
    import os
    from nipype.interfaces.base import Bunch
    from copy import deepcopy
    import numpy as np
    base_proj_dir = '/home/data/madlab/data/mri/wmaze/scanner_behav'
    output = []

    for curr_run in range(1,7):
        names = []
        onsets = []
        durations = []
        amplitudes = []

        data_fixed_corr = np.genfromtxt(base_proj_dir + '/{0}/model_GLM2/run{1}_fixed_corr.txt'.format(subject_id, curr_run), dtype = str)
        data_fixed_incorr = np.genfromtxt(base_proj_dir + '/{0}/model_GLM2/run{1}_fixed_incorr.txt'.format(subject_id, curr_run), dtype = str)
        data_cond_corr = np.genfromtxt(base_proj_dir + '/{0}/model_GLM2/run{1}_cond_corr.txt'.format(subject_id, curr_run), dtype = str) 
        data_cond_incorr = np.genfromtxt(base_proj_dir + '/{0}/model_GLM2/run{1}_cond_incorr.txt'.format(subject_id, curr_run), dtype = str)
        data_all_BL = np.genfromtxt(base_proj_dir + '/{0}/model_GLM2/run{1}_all_BL.txt'.format(subject_id, curr_run), dtype = str)
        
        trial_type = ['fixed', 'cond']
        for curr_type in trial_type:
            corr_array_name = eval('data_{0}_corr'.format(curr_type))
            incorr_array_name = eval('data_{0}_incorr'.format(curr_type))    
            if incorr_array_name.size > 0: #more than 1 incorrect
                curr_names = ['{0}_corr'.format(curr_type), '{0}_incorr'.format(curr_type)]
                if corr_array_name.size == 3: #only 1 correct
                    curr_corr_onsets = [float(corr_array_name[0])]
                    curr_corr_durations = [float(corr_array_name[1])]
                    curr_corr_amplitudes = [float(corr_array_name[2])]
                else:
                    curr_corr_onsets = map(float, corr_array_name[:,0])
                    curr_corr_durations = map(float, corr_array_name[:,1])
                    curr_corr_amplitudes = map(float, corr_array_name[:,2])               
                if incorr_array_name.size == 3: # only 1 incorrect
                    curr_incorr_onsets = [float(incorr_array_name[0])]
                    curr_incorr_durations = [float(incorr_array_name[1])]
                    curr_incorr_amplitudes = [float(incorr_array_name[2])]                
                else: #more than 1 incorrect
                    curr_incorr_onsets = map(float, incorr_array_name[:,0])
                    curr_incorr_durations = map(float, incorr_array_name[:,1])
                    curr_incorr_amplitudes = map(float,incorr_array_name[:,2])
                curr_onsets = [curr_corr_onsets, curr_incorr_onsets]
                curr_durations = [curr_corr_durations, curr_incorr_durations]
                curr_amplitudes = [curr_corr_amplitudes, curr_incorr_amplitudes]
            else: #no incorrect
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
   
        curr_names = ['all_BL']
        curr_corr_onsets = map(float, data_all_BL[:,0])
        curr_corr_durations = map(float, data_all_BL[:,1])
        curr_corr_amplitudes = map(float, data_all_BL[:,2])
        curr_onsets = [curr_corr_onsets]
        curr_durations = [curr_corr_durations]
        curr_amplitudes = [curr_corr_amplitudes]         
        names.append(curr_names)  
        onsets.append(curr_onsets)
        durations.append(curr_durations)
        amplitudes.append(curr_amplitudes)
        

        if any(isinstance(el, list) for el in names): # Unpacks subarrays into one mega array
            names = [el for sublist in names for el in sublist]  
        if any(isinstance(el, list) for el in onsets):
            onsets = [el_o for sublist_o in onsets for el_o in sublist_o]
        if any(isinstance(el, list) for el in durations):
            durations = [el_d for sublist_d in durations for el_d in sublist_d]
        if any(isinstance(el, list) for el in amplitudes):
            amplitudes = [el_a for sublist_a in amplitudes for el_a in sublist_a]
 
        output.insert(curr_run, #insert the contents of each run at the index of curr_run (1-6)
                      Bunch(conditions = names,
                            onsets = deepcopy(onsets),
                            durations = deepcopy(durations),
                            amplitudes = deepcopy(amplitudes),
                            tmod = None, pmod = None, regressor_names = None, regressors = None))
    return output

#function to obtain and create contrasts *flexibly* in case there are not enough incorrect trials
def get_contrasts(subject_id, info):
    contrasts = []
    for i, j in enumerate(info): #for each bunch received from subjectinfo function in get_contrasts node
        curr_run_contrasts = []
        #create contrast using a t-test, j.conditions (names received from Bunch), j.conditions is used to determine contrast dimensions 
        cont_all = ['AllVsBase', 'T', j.conditions, [1. / len(j.conditions)] * len(j.conditions)]
        curr_run_contrasts.append(cont_all)

        for curr_cond in j.conditions: #for each EV list name received from the bunch
            curr_cont = [curr_cond, 'T', [curr_cond], [1]]
            curr_run_contrasts.append(curr_cont) 
        if 'fixed_corr' in j.conditions and 'fixed_incorr' in j.conditions:
            cont_fixed_corr_vs_fixed_incorr = ['fixedCorr_minus_fixedIncorr', 'T', ['fixed_corr', 'fixed_incorr'], [1, -1]]
            cont_fixed_incorr_vs_fixed_corr = ['fixedIncorr_minus_fixedCorr', 'T', ['fixed_corr', 'fixed_incorr'], [-1, 1]]
            cont_all_fixed = ['all_fixed', 'T', ['fixed_corr','fixed_incorr'], [1./2, 1./2]]
            curr_run_contrasts.append(cont_fixed_corr_vs_fixed_incorr)
            curr_run_contrasts.append(cont_fixed_incorr_vs_fixed_corr)
            curr_run_contrasts.append(cont_all_fixed)                     
        if 'cond_corr' in j.conditions and 'cond_incorr' in j.conditions:
            cont_cond_corr_vs_cond_incorr = ['condCorr_minus_condIncorr', 'T', ['cond_corr', 'cond_incorr'], [1, -1]]
            cont_cond_incorr_vs_cond_corr = ['condIncorr_minus_condCorr', 'T', ['cond_corr', 'cond_incorr'], [-1, 1]]
            cont_all_cond = ['all_cond', 'T', ['cond_corr','cond_incorr'], [1./2, 1./2]]
            curr_run_contrasts.append(cont_cond_corr_vs_cond_incorr)
            curr_run_contrasts.append(cont_cond_incorr_vs_cond_corr)
            curr_run_contrasts.append(cont_all_cond)               
        if 'fixed_corr' in j.conditions and 'cond_corr' in j.conditions:
            cont_fixed_corr_vs_cond_corr = ['fixedCorr_minus_condCorr', 'T', ['fixed_corr', 'cond_corr'], [1, -1]]
            cont_cond_corr_vs_fixed_corr = ['condCorr_minus_fixedCorr', 'T', ['fixed_corr', 'cond_corr'], [-1, 1]]
            cont_all_corr = ['all_corr', 'T', ['fixed_corr','cond_corr'], [1./2, 1./2]]
            curr_run_contrasts.append(cont_fixed_corr_vs_cond_corr)
            curr_run_contrasts.append(cont_cond_corr_vs_fixed_corr)
            curr_run_contrasts.append(cont_all_corr) 
        if 'fixed_incorr' in j.conditions and 'cond_incorr' in j.conditions:
            cont_fixed_incorr_vs_cond_incorr = ['fixedIncorr_minus_condIncorr', 'T', ['fixed_incorr', 'cond_incorr'], [1, -1]]
            cont_cond_incorr_vs_fixed_incorr = ['condIncorr_minus_fixedIncorr', 'T', ['fixed_incorr', 'cond_incorr'], [-1, 1]]
            cont_all_incorr = ['all_incorr', 'T', ['fixed_incorr','cond_incorr'], [1./2, 1./2]]
            curr_run_contrasts.append(cont_fixed_incorr_vs_cond_incorr)
            curr_run_contrasts.append(cont_cond_incorr_vs_fixed_incorr)  
            curr_run_contrasts.append(cont_all_incorr)   
	#if all conditions exist in Bunch           
        if 'fixed_corr' in j.conditions and 'cond_corr' in j.conditions and 'fixed_incorr' in j.conditions and 'cond_incorr' in j.conditions: 
            cont_all_corr_vs_all_incorr = ['allCorr_minus_allIncorr', 'T', ['fixed_corr','cond_corr', 'fixed_incorr', 'cond_incorr'], 
                                           [1./2, 1./2, -1./2, -1./2]]           
            cont_all_incorr_vs_all_corr = ['allIncorr_minus_allCorr', 'T', ['fixed_corr','cond_corr', 'fixed_incorr', 'cond_incorr'], 
                                           [-1./2, -1./2, 1./2, 1./2]] 
            cont_all_fixed_vs_all_cond = ['allFixed_minus_allCond', 'T', ['fixed_corr','cond_corr', 'fixed_incorr', 'cond_incorr'], 
                                          [1./2, -1./2, 1./2, -1./2]]           
            cont_all_cond_vs_all_fixed = ['allCond_minus_allFixed', 'T', ['fixed_corr','cond_corr', 'fixed_incorr', 'cond_incorr'], 
                                          [-1./2, 1./2, -1./2, 1./2]] 
            curr_run_contrasts.append(cont_all_corr_vs_all_incorr)
            curr_run_contrasts.append(cont_all_incorr_vs_all_corr)
            curr_run_contrasts.append(cont_all_fixed_vs_all_cond)
            curr_run_contrasts.append(cont_all_cond_vs_all_fixed)
        contrasts.append(curr_run_contrasts)
    return contrasts
                                                                          

def get_subs(cons): #function for naming the output types
    subs = []
    for run_cons in cons: #for each run
        run_subs = []
        for i, con in enumerate(run_cons): #for each contrast in the run
            #append a tuple containing "cope#" and "cope#+name" 
            run_subs.append(('cope%d.'%(i + 1), 'cope%02d_%s.'%(i + 1, con[0])))
            run_subs.append(('varcope%d.'%(i + 1), 'varcope%02d_%s.'%(i + 1, con[0])))
            run_subs.append(('zstat%d.'%(i + 1), 'zstat%02d_%s.'%(i + 1, con[0])))
            run_subs.append(('tstat%d.'%(i + 1), 'tstat%02d_%s.'%(i + 1, con[0])))
        subs.append(run_subs)        
    return subs


#function for extracting the motion parameters from the noise files
def motion_noise(subjinfo, files):
    import numpy as np
    motion_noise_params = []
    motion_noi_par_names = []
    if not isinstance(files, list):
        files = [files]
    if not isinstance(subjinfo, list):
        subjinfo = [subjinfo]
    for j,i in enumerate(files):
        curr_mot_noi_par_names = ['Pitch (rad)', 'Roll (rad)', 'Yaw (rad)', 'Tx (mm)', 'Ty (mm)', 'Tz (mm)',
                                  'Pitch_1d', 'Roll_1d', 'Yaw_1d', 'Tx_1d', 'Ty_1d', 'Tz_1d',
                                  'Norm (mm)', 'LG_1stOrd', 'LG_2ndOrd', 'LG_3rdOrd', 'LG_4thOrd']
        a = np.genfromtxt(i)
        motion_noise_params.append([[]] * a.shape[1])
        if a.shape[1] > 17:
            for num_out in range(a.shape[1] - 17):
                out_name = 'out_{0}'.format(num_out + 1)
                curr_mot_noi_par_names.append(out_name)
        for z in range(a.shape[1]):
            motion_noise_params[j][z] = a[:, z].tolist()
        motion_noi_par_names.append(curr_mot_noi_par_names)
    for j,i in enumerate(subjinfo):
        if i.regressor_names == None: 
            i.regressor_names = []
        if i.regressors == None: 
            i.regressors = []
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
    frstlvl_wf = Workflow(name = 'frstlvl_wf')
    
    info = dict(task_mri_files = [['subject_id', 'wmaze']], #dictionary used in datasource
                motion_noise_files = [['subject_id']])


    #function node to call subjectinfo function with name, onset, duration, and amplitude info
    subject_info = Node(Function(input_names = ['subject_id'],  
                                 output_names = ['output'],
                                 function = subjectinfo),
                        name = 'subject_info')
    subject_info.inputs.ignore_exception = False
    subject_info.inputs.subject_id = subject_id


    #function node to define contrasts
    getcontrasts = Node(Function(input_names = ['subject_id', 'info'],  
                                 output_names = ['contrasts'],
                                 function = get_contrasts),
                        name = 'getcontrasts')
    getcontrasts.inputs.ignore_exception = False
    getcontrasts.inputs.subject_id = subject_id
    frstlvl_wf.connect(subject_info, 'output', getcontrasts, 'info')


    #function node to substitute names of folders and files created during pipeline
    getsubs = Node(Function(input_names = ['cons'],
                            output_names = ['subs'],
                            # Calls the function 'get_subs'
                            function = get_subs),
                   name = 'getsubs')
    getsubs.inputs.ignore_exception = False
    getsubs.inputs.subject_id = subject_id
    frstlvl_wf.connect(subject_info, 'output', getsubs, 'info')
    frstlvl_wf.connect(getcontrasts, 'contrasts', getsubs, 'cons')

    

    #datasource node to get task_mri and motion-noise files
    datasource = Node(DataGrabber(infields = ['subject_id'], 
                                  outfields = info.keys()), 
                      name = 'datasource')
    datasource.inputs.template = '*'
    datasource.inputs.subject_id = subject_id
    datasource.inputs.base_directory = os.path.abspath('/home/data/madlab/data/mri/wmaze/preproc/')
    datasource.inputs.field_template = dict(task_mri_files = '%s/func/smoothed_fullspectrum/_maskfunc2*/*%s*.nii.gz', #functional files
                                            motion_noise_files = '%s/noise/filter_regressor??.txt') #filter regressor noise files
    datasource.inputs.template_args = info
    datasource.inputs.sort_filelist = True
    datasource.inputs.ignore_exception = False
    datasource.inputs.raise_on_empty = True


    #function node to remove last three volumes from functional data
    fslroi_epi = MapNode(ExtractROI(t_min = 0, t_size = 197),  #start from first volume and end on -3
                         iterfield = ['in_file'],
                         name = 'fslroi_epi')
    fslroi_epi.output_type = 'NIFTI_GZ'
    fslroi_epi.terminal_output = 'stream'
    frstlvl_wf.connect(datasource, 'task_mri_files', fslroi_epi, 'in_file')


    #function node to modify the motion and noise files to be single regressors
    motionnoise = Node(Function(input_names = ['subjinfo', 'files'],
                                output_names = ['subjinfo'],
                                function = motion_noise),
                       name = 'motionnoise')
    motionnoise.inputs.ignore_exception = False
    frstlvl_wf.connect(subject_info, 'output', motionnoise, 'subjinfo')
    frstlvl_wf.connect(datasource, 'motion_noise_files', motionnoise, 'files')


    #node to create model specifications compatible with spm/fsl designers (requires subjectinfo to be received in the form of a Bunch)
    specify_model = Node(SpecifyModel(), 
                         name = 'specify_model')
    specify_model.inputs.high_pass_filter_cutoff = -1.0 #high-pass filter cutoff in seconds
    specify_model.inputs.ignore_exception = False
    specify_model.inputs.input_units = 'secs' #input units in either 'secs' or 'scans'
    specify_model.inputs.time_repetition = 2.0 #TR
    frstlvl_wf.connect(fslroi_epi, 'roi_file', specify_model, 'functional_runs') #editted data files for model -- list of 4D files
    #list of event description files in 3 column format corresponding to onsets, durations, and amplitudes 
    frstlvl_wf.connect(motionnoise, 'subjinfo', specify_model, 'subject_info')

    
    #node for basic interface class generating identity mappings
    modelfit_inputspec = Node(IdentityInterface(fields = ['session_info', 'interscan_interval', 'contrasts', 'film_threshold', 
                                                          'functional_data', 'bases', 'model_serial_correlations'], 
                                                mandatory_inputs = True),
                              name = 'modelfit_inputspec')
    modelfit_inputspec.inputs.bases = {'dgamma':{'derivs': False}}
    modelfit_inputspec.inputs.film_threshold = 0.0 
    modelfit_inputspec.inputs.interscan_interval = 2.0
    modelfit_inputspec.inputs.model_serial_correlations = True
    frstlvl_wf.connect(fslroi_epi, 'roi_file', modelfit_inputspec, 'functional_data')
    frstlvl_wf.connect(getcontrasts, 'contrasts', modelfit_inputspec, 'contrasts')
    frstlvl_wf.connect(specify_model, 'session_info', modelfit_inputspec, 'session_info')
   

    #node for first level SPM design matrix to demonstrate contrasts and motion/noise regressors
    level1_design = MapNode(Level1Design(), iterfield = ['contrasts', 'session_info'],
                            name = 'level1_design')
    level1_design.inputs.ignore_exception = False
    frstlvl_wf.connect(modelfit_inputspec, 'interscan_interval', level1_design, 'interscan_interval')
    frstlvl_wf.connect(modelfit_inputspec, 'session_info', level1_design, 'session_info')
    frstlvl_wf.connect(modelfit_inputspec, 'contrasts', level1_design, 'contrasts')
    frstlvl_wf.connect(modelfit_inputspec, 'bases', level1_design, 'bases')
    frstlvl_wf.connect(modelfit_inputspec, 'model_serial_correlations', level1_design, 'model_serial_correlations')
    

    #MapNode to generate a design.mat file for each run
    generate_model = MapNode(FEATModel(), iterfield = ['fsf_file', 'ev_files'],
                             name = 'generate_model') 
    generate_model.inputs.environ = {'FSLOUTPUTTYPE': 'NIFTI_GZ'}
    generate_model.inputs.ignore_exception = False
    generate_model.inputs.output_type = 'NIFTI_GZ'
    generate_model.inputs.terminal_output = 'stream' 
    frstlvl_wf.connect(level1_design, 'fsf_files', generate_model, 'fsf_file')
    frstlvl_wf.connect(level1_design, 'ev_files', generate_model, 'ev_files')
  

    #MapNode to estimate the model using FILMGLS -- fits the design matrix to the voxel timeseries
    estimate_model = MapNode(FILMGLS(), iterfield = ['design_file', 'in_file', 'tcon_file'],
                             name = 'estimate_model')
    estimate_model.inputs.environ = {'FSLOUTPUTTYPE': 'NIFTI_GZ'}
    estimate_model.inputs.ignore_exception = False
    estimate_model.inputs.mask_size = 5 #Susan-smooth mask size
    estimate_model.inputs.output_type = 'NIFTI_GZ'
    estimate_model.inputs.results_dir = 'results'
    estimate_model.inputs.smooth_autocorr = True #smooth auto-correlation estimates
    estimate_model.inputs.terminal_output = 'stream'
    frstlvl_wf.connect(modelfit_inputspec, 'film_threshold', estimate_model, 'threshold')
    frstlvl_wf.connect(modelfit_inputspec, 'functional_data', estimate_model, 'in_file')
    frstlvl_wf.connect(generate_model, 'design_file', estimate_model, 'design_file') #mat file containing ascii matrix for design
    frstlvl_wf.connect(generate_model, 'con_file', estimate_model, 'tcon_file') #contrast file containing contrast vectors


    #merge node to merge the contrasts - necessary for fsl 5.0.7 and greater
    merge_contrasts = MapNode(Merge(2), iterfield = ['in1'], 
                              name = 'merge_contrasts')
    frstlvl_wf.connect(estimate_model, 'zstats', merge_contrasts, 'in1')


    #MapNode to transform the z2pval
    z2pval = MapNode(ImageMaths(), iterfield = ['in_file'], 
                     name='z2pval')
    z2pval.inputs.environ = {'FSLOUTPUTTYPE': 'NIFTI_GZ'}
    z2pval.inputs.ignore_exception = False
    z2pval.inputs.op_string = '-ztop' #defines the operation used
    z2pval.inputs.output_type = 'NIFTI_GZ'
    z2pval.inputs.suffix = '_pval'
    z2pval.inputs.terminal_output = 'stream'
    frstlvl_wf.connect(merge_contrasts, ('out', pop_lambda), z2pval, 'in_file')


    #outputspec node using IdentityInterface() to receive information from estimate_model, merge_contrasts, z2pval, generate_model, and estimate_model
    modelfit_outputspec = Node(IdentityInterface(fields = ['copes', 'varcopes', 'dof_file', 'pfiles', 'parameter_estimates', 'zstats',
                                                           'design_image', 'design_file', 'design_cov', 'sigmasquareds'],
                                                 mandatory_inputs = True),
                               name = 'modelfit_outputspec')
    frstlvl_wf.connect(estimate_model, 'copes', modelfit_outputspec, 'copes') #lvl1 cope files
    frstlvl_wf.connect(estimate_model, 'varcopes', modelfit_outputspec, 'varcopes') #lvl1 varcope files
    frstlvl_wf.connect(merge_contrasts, 'out', modelfit_outputspec, 'zstats') #zstats across runs 
    frstlvl_wf.connect(z2pval, 'out_file', modelfit_outputspec, 'pfiles')
    frstlvl_wf.connect(generate_model, 'design_image', modelfit_outputspec, 'design_image') #graphical representation of design matrix
    frstlvl_wf.connect(generate_model, 'design_file', modelfit_outputspec, 'design_file') #mat file containing ascii matrix for design
    frstlvl_wf.connect(generate_model, 'design_cov', modelfit_outputspec, 'design_cov') #graphical representation of design covariance
    frstlvl_wf.connect(estimate_model, 'param_estimates', modelfit_outputspec, 'parameter_estimates') #parameter estimates for columns of design matrix
    frstlvl_wf.connect(estimate_model, 'dof_file', modelfit_outputspec, 'dof_file') #degrees of freedom
    frstlvl_wf.connect(estimate_model, 'sigmasquareds', modelfit_outputspec, 'sigmasquareds') #summary of residuals


    #datasink node to save output from multiple points in the pipeline
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

def create_frstlvl_workflow(args, name = 'GLM2_frstlvl'):
    kwargs = dict(subject_id = args.subject_id,
                  sink_directory = os.path.abspath(args.out_dir),
                  name = name)
    frstlvl_workflow = firstlevel_wf(**kwargs)
    return frstlvl_workflow

if __name__ == "__main__":
    from argparse import ArgumentParser
    parser = ArgumentParser(description = __doc__)
    parser.add_argument("-s", "--subject_id", dest = "subject_id", help = "Current subject id", required = True)
    parser.add_argument("-o", "--output_dir", dest = "out_dir", help = "Output directory base")
    parser.add_argument("-w", "--work_dir", dest = "work_dir", help = "Working directory base")
    args = parser.parse_args()

    wf = create_frstlvl_workflow(args)

    if args.work_dir:
        work_dir = os.path.abspath(args.work_dir)    
    else:
        work_dir = os.getcwd()

    wf.config['execution']['crashdump_dir'] = '/scratch/madlab/crash/mandy_crash/model_GLM2/lvl1'
    wf.base_dir = work_dir + '/' + args.subject_id
    wf.run(plugin='SLURM', plugin_args={'sbatch_args': ('-p investor --qos pq_madlab -N 1 -n 1'), 'overwrite': True})
