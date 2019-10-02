#!/usr/bin/env python

"""
=================================================
GLM3_fMRI: Fixed before Conditional -- Model GLM1
=================================================
Group level (Random Effects) workflow for UM GE 750 wmaze task data.

- Model_GLM1 
  - Use FSL ROI to recreate EPI data, removing last 3 volumes
  - Removed last 3 trials before EV creation
  - EV directory (Model_GLM1) --- /home/data/madlab/data/mri/wmaze/scanner_behav/WMAZE_001/model_GLM1


- python GLM1_grplvl.py -s WMAZE_001
                         -o /home/data/madlab/data/mri/wmaze/grp_lvl/model_GLM1
                         -w /scratch/madlab/crash/model_GLM1
 
"""

from nipype.pipeline.engine import Workflow, Node, MapNode
from nipype.interfaces.utility import IdentityInterface, Merge
from nipype.interfaces.io import DataGrabber, DataSink
from nipype.interfaces import fsl
from nipype.interfaces.fsl.model import L2Model, FLAMEO, Randomise
from nipype.interfaces.fsl.utils import ImageMaths


###############
## Functions ##
###############


get_len = lambda x: len(x) #get length


def pickfirst(func): #pick first volume in a timeseries
    if isinstance(func, list):
        return func[0]
    else:
        return func


def get_substitutions(contrast):
    subs = [('_contrast{0}'.format(contrast),''), ('output','')]
    for i in range(0, 23):
        subs.append(('_z2pval{0}'.format(i),''))
        subs.append(('_cluster{0}'.format(i), ''))
        subs.append(('_fdr{0}'.format(i),''))
    return subs


contrasts = ['all_before_B_corr', 'all_before_B_incorr', 'all_corr_minus_all_incorr', 'all_incorr_minus_all_corr', 'all_remaining']


proj_dir = '/home/data/madlab/data/mri/wmaze'
fs_projdir = '/home/data/madlab/surfaces/wmaze'
work_dir = '/scratch/madlab/wmaze/grplvl/model_GLM1/'

sids = ['WMAZE_001', 'WMAZE_002', 'WMAZE_004', 'WMAZE_005', 'WMAZE_006', 'WMAZE_007', 'WMAZE_008', 'WMAZE_009', 'WMAZE_010', 'WMAZE_012',  
        'WMAZE_017', 'WMAZE_018', 'WMAZE_019', 'WMAZE_020', 'WMAZE_021', 'WMAZE_022', 'WMAZE_023', 'WMAZE_024', 'WMAZE_026', 'WMAZE_027']


group_wf = Workflow('group_wf')
group_wf.base_dir = work_dir


#node to iterate through all contrasts
contrast_iterable = Node(IdentityInterface(fields = ['contrast'], 
                                           mandatory_inputs = True), 
                         name = 'contrast_iterable')
contrast_iterable.iterables = ('contrast', contrasts)


#dictionary keys for the datasource node
info = dict(copes = [['subject_id', 'contrast']], varcopes = [['subject_id', 'contrast']])
#node to grab cope and varcope data for each subject and contrast
datasource = Node(DataGrabber(infields = ['subject_id', 'contrast'],
                              outfields = info.keys()),
                  name = 'datasource')
datasource.inputs.base_directory = proj_dir
datasource.inputs.field_template = dict(copes = 'norm_stats/model_GLM1/%s/norm_copes/cope_%s_trans.nii.gz',
                                        varcopes = 'norm_stats/model_GLM1/%s/norm_varcopes/varcope_%s_trans.nii.gz')
datasource.inputs.ignore_exception = False
datasource.inputs.raise_on_empty = True
datasource.inputs.sort_filelist = True
datasource.inputs.template = '*'
datasource.inputs.template_args = info
datasource.inputs.subject_id = sids
group_wf.connect(contrast_iterable, 'contrast', datasource, 'contrast')


#identity interface node to hold and store information for input into future nodes
inputspec = Node(IdentityInterface(fields = ['copes', 'varcopes', 'brain_mask', 'run_mode'],
                                   mandatory_inputs = True),
                 name = 'inputspec')
inputspec.inputs.brain_mask = '/home/data/madlab/data/mri/wmaze/wmaze_T1_template/wmaze_grptemplate_mask.nii.gz' #anatomical group template mask
inputspec.inputs.run_mode = 'flame1'
group_wf.connect(datasource, 'copes', inputspec, 'copes')
group_wf.connect(datasource, 'varcopes', inputspec, 'varcopes')


#node to concatenate varcopes into single image across time
grp_merge_varcopes = Node(fsl.utils.Merge(), name = 'grp_merge_varcopes')
grp_merge_varcopes.inputs.dimension = 't' #concatenate across time
grp_merge_varcopes.inputs.environ = {'FSLOUTPUTTYPE': 'NIFTI_GZ'}
grp_merge_varcopes.inputs.ignore_exception = False
grp_merge_varcopes.inputs.output_type = 'NIFTI_GZ'
grp_merge_varcopes.inputs.terminal_output = 'stream'
group_wf.connect(inputspec, 'varcopes', grp_merge_varcopes, 'in_files')


#node for group-specific level 2 model 
grp_l2model = Node(L2Model(), name = 'grp_l2model')
grp_l2model.inputs.ignore_exception = False
group_wf.connect(inputspec, ('copes', get_len), grp_l2model, 'num_copes')


#node to concatenate copes into single image across time
grp_merge_copes = Node(fsl.utils.Merge(), name = 'grp_merge_copes')
grp_merge_copes.inputs.dimension = 't' #concatenate across time
grp_merge_copes.inputs.environ = {'FSLOUTPUTTYPE': 'NIFTI_GZ'}
grp_merge_copes.inputs.ignore_exception = False
grp_merge_copes.inputs.output_type = 'NIFTI_GZ'
grp_merge_copes.inputs.terminal_output = 'stream'
group_wf.connect(inputspec, 'copes', grp_merge_copes, 'in_files')


#node to run Randomise
grp_randomise = Node(fsl.Randomise(), name = 'grp_randomise')
grp_randomise.inputs.environ = {'FSLOUTPUTTYPE': 'NIFTI_GZ'}
grp_randomise.inputs.ignore_exception = False
grp_randomise.inputs.tfce = True
grp_randomise.inputs.base_name = 'oneSampT'
grp_randomise.inputs.num_perm = 5000
grp_randomise.inputs.output_type = 'NIFTI_GZ'
grp_randomise.inputs.terminal_output = 'stream'
grp_randomise.plugin_args = {'bsub_args': '-m IB_40C_1.5T_1'}
group_wf.connect(grp_l2model, 'design_mat', grp_randomise, 'design_mat')
group_wf.connect(grp_l2model, 'design_con', grp_randomise, 'tcon')
group_wf.connect(grp_merge_copes, 'merged_file', grp_randomise, 'in_file')
group_wf.connect(inputspec, 'brain_mask', grp_randomise, 'mask')


#node for group_randomise.sinker
group_randomise_sinker = Node(DataSink(infields = None), name = 'group_randomise_sinker')
group_randomise_sinker.inputs.base_directory = '/home/data/madlab/data/mri/wmaze/grplvl/model_GLM1_randomisels'
group_randomise_sinker.inputs.ignore_exception = False
group_randomise_sinker.inputs.parameterization = True
group_wf.connect(grp_randomise, 't_corrected_p_files', group_randomise_sinker, 'output.corrected.@tcorr_p_files')
group_wf.connect(grp_randomise, 'tstat_files', group_randomise_sinker, 'output.@tstat_files')
group_wf.connect(contrast_iterable, 'contrast', group_randomise_sinker, 'container')

group_wf.config['execution']['crashdump_dir'] = work_dir
group_wf.base_dir = work_dir
group_wf.run(plugin='SLURM', plugin_args={'sbatch_args': ('-p investor --qos pq_madlab -N 1 -n 1'), 'overwrite': True})
