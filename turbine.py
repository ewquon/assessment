"""
Functions for assessing turbine performance and loads
"""
import os
import random
from datatools.codedrivers import InputTemplate

class OpenFAST(object):
    """Manages OpenFAST aeroelastic simulation inputs and outputs"""

    def __init__(self,dpath='.',Nruns=1,start_seed=12345,verbose=True):
        """Set up simulation from `dpath`, with a sweep of `Nruns`
        corresponding to unique TurbSim inflow simulations
        """
        self.cwd = dpath
        random.seed(start_seed)
        self.seeds = [ random.randint(-2147483648,2147483647)
                       for _ in range(Nruns) ]
        self.verbose = verbose

    def _generate_input(self,inputfile,templatefile,inputs={}):
        tmp = InputTemplate(templatefile)
        tmp_inputs = tmp.get_fields() # returns {field: format_str}
        fields_to_set = list(tmp_inputs.keys())
        for setkey,setval in inputs.items():
            if setkey in tmp_inputs.keys():
                if self.verbose:
                    print('  {:s} = {:g} (format: {:s})'.format(
                            setkey,setval,tmp_inputs[setkey]))
                tmp_inputs[setkey] = setval
                fields_to_set.remove(setkey)
            else:
                raise KeyError("Ignored input for '" + setkey + 
                               "' (not in template file)")
        if len(fields_to_set) > 0:
            raise KeyError('The following substitution fields were not set: "'
                           +'", "'.join(fields_to_set)+'"')
        # at this point, the template inputs (tmp_inputs) are completely filled
        tmp.generate(inputfile,replace=tmp_inputs)
        return tmp
