"""
Functions for assessing turbine performance and loads
"""
import os
import random
import subprocess

from datatools.codedrivers import InputTemplate

class OpenFAST(object):
    """Manages OpenFAST aeroelastic simulation inputs and outputs"""

    def __init__(self,dpath='.',Nruns=1,start_seed=12345,verbose=True):
        """Set up simulation from `dpath`, with a sweep of `Nruns`
        corresponding to unique TurbSim inflow simulations
        """
        self.verbose = verbose
        self.cwd = dpath
        self.inflow = None
        self.Nruns = Nruns
        # integer range from turbsim manual
        random.seed(start_seed)
        self.seeds = [ random.randint(-2147483648, 2147483647)
                       for _ in range(Nruns) ]

    def _generate_input(self,inputfile,templatefile,inputs={}):
        tmp = InputTemplate(templatefile)
        tmp_inputs = tmp.get_fields() # returns {field: format_str}
        fields_to_set = list(tmp_inputs.keys())
        for setkey,setval in inputs.items():
            if setkey in tmp_inputs.keys():
                if self.verbose:
                    outstr = '  {:s} = {:'+tmp_inputs[setkey][-1]+'} (format: {:s})'
                    print(outstr.format(setkey,setval,tmp_inputs[setkey]))
                tmp_inputs[setkey] = setval
                fields_to_set.remove(setkey)
            else:
                raise KeyError("Ignored input for '" + setkey + 
                               "' (not in " + templatefile + " file)")
        if len(fields_to_set) > 0:
            raise KeyError('The following substitution fields were not set: "'
                           +'", "'.join(fields_to_set)+'"')
        # at this point, the template inputs (tmp_inputs) are completely filled
        tmp.generate(inputfile,replace=tmp_inputs)
        return tmp

    def setup_turbsim(self,inputs={},
                      inflowdir='Wind',
                      template='start.inp',
                      prefix='turbsim'):
        """Setup all turbsim input files for all seeds"""
        self.inflowdir = inflowdir
        self.ts_inputfiles = [
            os.path.join(self.cwd, self.inflowdir, '{}_{:02d}.inp'.format(prefix,irun))
            for irun in range(self.Nruns)
        ]
        templatefile = os.path.join(self.cwd, self.inflowdir, template)
        for inputfile,seed in zip(self.ts_inputfiles,self.seeds):
            inputs['RandSeed1'] = seed
            if self.verbose:
                print('Generating',inputfile,'from',templatefile)
            self._generate_input(inputfile,templatefile,inputs)
        self.inflow = 'turbsim'

    def run_turbsim(self,iseed):
        """Run turbsim with pre-generated turbulence seed"""
        inputfile = os.path.split(self.ts_inputfiles[iseed])[1]
        logfile = 'log.' + os.path.splitext(inputfile)[0]
        logpath = os.path.join(self.cwd, self.inflowdir, logfile)
        if self.verbose:
            print('{}$ turbsim {} > {} &'.format(os.path.join(self.cwd,self.inflowdir),
                                                 inputfile,logfile))
        proc = subprocess.Popen(['turbsim', inputfile],
                                cwd=os.path.join(self.cwd, self.inflowdir),
                                stdout=subprocess.PIPE)
        with open(logpath,'wb') as f:
            okay = False
            for line in proc.stdout:
                f.write(line)
                if line.decode().strip() == 'TurbSim terminated normally.':
                    okay = True
        istat = proc.poll() # get returncode
        if (not okay) or (istat != 0):
            raise RuntimeError('termination string found={}, return code={}'.format(okay,istat))
        return proc

    def run(self,i):
        """Run specified simulation (inflow, openfast)"""
        # setup inflow, if needed
        if self.inflow == 'turbsim':
            self.run_turbsim(i)
        else:
            raise RuntimeError('Need to setup inflow')
        # run openfast

    def run_all(self):
        """Run all simulations after setup routines have been called"""
        for irun in range(self.Nruns):
            self.run(irun)

