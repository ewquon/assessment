"""
Functions for assessing turbine performance and loads
"""
import os
import random
import subprocess
from multiprocessing import Pool

import pandas as pd
from datatools.codedrivers import InputTemplate
from datatools.FAST.output import read

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
        self.parallel = False
        self.outputs = None
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
                                stdout=subprocess.PIPE, text=True)
        okay = False
        with open(logpath,'w') as f:
            for line in proc.stdout:
                f.write(line)
                if line.strip() == 'TurbSim terminated normally.':
                    okay = True
        istat = proc.poll() # get returncode
        if (not okay) or (istat != 0):
            raise RuntimeError('termination string found={}, return code={}'.format(okay,istat))
        return proc

    def _setup_openfast(self,irun):
        """Setup inputs for new openfast run, return input file to be
        used when calling openfast
        """
        inflowfile = 'InflowWind_{:02d}.dat'.format(irun)
        inflowpath = os.path.join(self.cwd, inflowfile)
        if self.verbose:
            print('Generating',inflowpath)
        if self.inflow == 'turbsim':
            # TurbSim synthetic turbulence with binary flowfield input
            inflowtemplate = os.path.join(self.cwd, 'InflowWind_bts.dat')
            tsinput = os.path.split(self.ts_inputfiles[irun])[1]
            btsfile = os.path.splitext(tsinput)[0] + '.bts'
            btspath = os.path.join(self.inflowdir, btsfile)
            inputs = {
                'BTSFilename': btspath
            }
            self._generate_input(inflowpath, inflowtemplate, inputs)
        else:
            raise RuntimeError('Unexpected inflow type: '+self.inflow)

        fstfile = 'run{:02d}.fst'.format(irun)
        fstpath = os.path.join(self.cwd, fstfile)
        if self.verbose:
            print('Generating',fstpath)
        fsttemplate = os.path.join(self.cwd, 'start.fst')
        inputs = {
            'InflowFile': inflowfile
        }
        self._generate_input(fstpath, fsttemplate, inputs)

        return fstfile

    def run(self,i):
        """Run specified simulation (inflow, openfast)"""
        # setup inflow, if needed
        if self.inflow == 'turbsim':
            self.run_turbsim(i)
        else:
            assert self.inflow is None
            raise RuntimeError('Need to setup inflow')
        # run openfast
        fstfile = self._setup_openfast(i)
        logfile = 'log.' + os.path.splitext(fstfile)[0]
        logpath = os.path.join(self.cwd, logfile)
        if self.verbose:
            print('{}$ openfast {} > {} &'.format(self.cwd,fstfile,logfile))
        proc = subprocess.Popen(['openfast', fstfile],
                                cwd=self.cwd,
                                stdout=subprocess.PIPE, text=True)
        okay = False
        with open(logpath,'w') as f:
            for line in proc.stdout:
                #print(line.rstrip()) #DEBUG
                f.write(line)
                line = line.strip()
                if self.verbose and line.startswith('Time:'):
                    if self.parallel:
                        line = '[{}] {}'.format(fstfile,line)
                    print(line)
                if line == 'OpenFAST terminated normally.':
                    okay = True
        istat = proc.poll() # get returncode
        if (not okay) or (istat != 0):
            raise RuntimeError('termination string found={}, return code={}'.format(okay,istat))
        return proc

    def run_all(self,procs=1):
        """Run all simulations after setup routines have been called"""
        self.parallel = (procs > 1)
        if self.parallel:
            with Pool(procs) as pool:
                pool.map(self.run, range(self.Nruns))
        else:
            for irun in range(self.Nruns):
                self.run(irun)

    def read_outputs(self):
        """Read all simulation outputs and return dataframe"""        
        dflist = []
        for irun in range(self.Nruns):
            outfile = os.path.join(self.cwd, 'run{:02d}.out'.format(irun))
            df = read(outfile).to_dataframe()
            df['run'] = irun
            dflist.append(df)
        self.outputs =  pd.concat(dflist)
        return self.outputs
