#!/usr/bin/env python
##### Parse raw SWiFT TTU tower data by the hour for 24 hours...
import os
import sys
import numpy as np
import pandas as pd

from mmctools.measurements.metmast import tilt_correction

# templates for writing out data in the legacy MMC ASCII format
from mmctools.mmcdata import header, record, datarow

#==============================================================================
# Information specific to TTU site

# measurement locations
ttu_lat,ttu_lon = 33.6105,-102.0505
ftlevels = [3,8,13,33,55,155,245,382,519,656] # sonic heights [ft]

# sampling information
minutesPerFile = 60
sampleRateRaw = 50 # [Hz]
sampleRateTarg = 1

dap_filenames = 'tower.z01.00.%Y%m%d.%H0000.ttu200m.dat'
starttimes = np.arange(24)              # 00, 01, ..., 23
endtimes = np.mod(np.arange(1,25), 24)  # 01, 02, ..., 23, 00
varnames = ['unorth','vwest','w','ustream','vcross','wdir','tsonic','t','p','rh']

# output options
subSampleByMean = False
dummyval = -999 # for missing values

#JAS 1108-1111, 4-day tilt-corrected
reg_coefs = [[-0.02047518907375512, -0.011649366757767144, -0.005668625739156408],
             [-0.10467766095942455, -0.0010341521077107858, -0.03058912859410552],
             [0.01667915952069285, 0.005848208752347085, 0.006706449805682085],
             [0.03109302695107044, -0.0010297838685371808, 0.006173865882031913],
             [0.0652410809553023, 0.0009344061198990692, -0.0007300303260188616],
             [0.11644312251929698, -0.010642857833143332, 0.004278938434437668],
             [0.14503074198177446, -0.008678657118724405, 0.018625128308748237],
             [0.17950082482974902, -0.014857133643938156, 0.012520780908011505],
             [0.2464041495610511, -0.037471231121111864, 0.012055903868292708],
             [0.2770725270201596, -0.004728345168161448, 0.01770705056549219]]
tilts = [[0.012954624102180665, 0.4528733026774165],
         [0.03059705313218443, 1.5370013668280538],
         [0.008897968050189109, -2.2879403125120583],
         [0.0062590775316462705, -1.405520595252335],
         [0.0011857730625258979, 2.4783726846562715],
         [0.011470318042450842, -0.38227054372399627],
         [0.020544967485295315, -1.1347455430302287],
         [0.01942702745609606, -0.7002672837032288],
         [0.0393425898140506, -0.31127834356150985],
         [0.01832543831154384, -1.3098530959146042]]


#==============================================================================

def TTURawToMMC(dpath,startdate,outpath):
    """Read files with 'dap_filenames' format corresponding to
    'startdate' from 'dpath', write out MMC data to 'outpath', which
    may be either a file path or a directory path (a default filename
    will be generated).
    """
    startdate = pd.to_datetime(startdate)
    dateStr = startdate.strftime('%Y-%m-%d')
    print("dateStr = {:s}".format(dateStr))
    z = 0.3048*np.array(ftlevels)
    Nz = len(z)
    datacolumns = pd.MultiIndex.from_product([z,varnames],names=['height',None])
    secondsPerMinute = 60
    signalRawSamples = sampleRateRaw*secondsPerMinute*minutesPerFile
    signalTargSamples = sampleRateTarg*secondsPerMinute*minutesPerFile
    sampleStride = int(sampleRateRaw/sampleRateTarg)

    sampletimes = []

    #declare and initialize mean arrays to zero
    # TODO: can rewrite code without these declared arrays
    um = np.zeros((Nz,signalTargSamples))
    vm = np.zeros((Nz,signalTargSamples))
    wm = np.zeros((Nz,signalTargSamples))
    usm = np.zeros((Nz,signalTargSamples))
    vcm = np.zeros((Nz,signalTargSamples))
    wdm = np.zeros((Nz,signalTargSamples))
    tsm = np.zeros((Nz,signalTargSamples))
    tm = np.zeros((Nz,signalTargSamples))
    thm = np.zeros((Nz,signalTargSamples))
    pm = np.zeros((Nz,signalTargSamples))
    rhm = np.zeros((Nz,signalTargSamples))
    uf = np.zeros((Nz,signalTargSamples))
    vf = np.zeros((Nz,signalTargSamples))
    wf = np.zeros((Nz,signalTargSamples))
    tf = np.zeros((Nz,signalTargSamples))
    thf = np.zeros((Nz,signalTargSamples))
    pf = np.zeros((Nz,signalTargSamples))
    auxf = np.zeros((Nz,signalTargSamples))
    tkem = np.zeros((Nz,signalTargSamples))
    tau11 = np.zeros((Nz,signalTargSamples))
    tau12 = np.zeros((Nz,signalTargSamples))
    tau13 = np.zeros((Nz,signalTargSamples))
    tau22 = np.zeros((Nz,signalTargSamples))
    tau23 = np.zeros((Nz,signalTargSamples))
    tau33 = np.zeros((Nz,signalTargSamples))
    hflux = np.zeros((Nz,signalTargSamples)) 
 
    # these fields were not sampled
    tkem[:] = dummyval
    tau11[:] = dummyval
    tau12[:] = dummyval
    tau13[:] = dummyval
    tau23[:] = dummyval
    tau22[:] = dummyval
    tau33[:] = dummyval
    hflux[:] = dummyval

    #Open the output file
    if os.path.isdir(outpath):
        # if we got an output directory, generate default filename and tack it
        # onto the end of the output dir path
        outfilename = startdate.strftime('TTU200m_%Y_%m%d-1Hz.dat')
        outpath = os.path.join(outpath,outfilename)
    fout = open(outpath,'w')

    #
    # Write the MMC file-header metadata
    #
    fout.write(header.format(
        institution='SNL',
        location='TTUTOWER',
        latitude=ttu_lat,
        longitude=ttu_lon,
        codename='TOWER',
        codetype='DATA',
        casename='DIURNAL',
        benchmark='CASE1',
        levels=len(z),
    ))

    ### For each hourly 50Hz file of TTU data...
    for starttime,endtime in zip(starttimes,endtimes):
        startdate = startdate.replace(hour=starttime)
        # get dap filename for current start date
        # e.g., 'tower.z01.00.20131108.000000.ttu200m.dat'
        filename = startdate.strftime(dap_filenames)
        fpath = os.path.join(dpath,filename)

        # read data file, which is in wide format, has column headers in the 5th
        # row (irow=4), and datetimes in the first column (icol=0). Column
        # names have variables changing fastest, then heights, i.e.,
        #   unorth_3ft,vwest_3ft,...,unorth_8ft,vwest_8ft,...
        df = pd.read_csv(fpath,skiprows=5,header=None,
                         parse_dates={'datetime':[0]})
        df = df.set_index('datetime')
        df.columns = datacolumns
        df = df.reorder_levels([1,0],axis=1).sort_index(axis=1)
        
        # now columns have heights changing fastest
        # - time-height data may be selected by column name
        #   e.g., df['unorth'] has array data with shape (Nt,Nz)
        # - note: for each raw TTU u_zonal = vsonic, and v_meridional = -usonic
        # - note: the remainder of this function assumes arrays have dimensions (height,time)
        u = df['vwest'].values.T
        v = -df['unorth'].values.T
        w = df['w'].values.T
        us = df['ustream'].values.T
        vc = df['vcross'].values.T
        wd = df['wdir'].values.T
        ts = df['tsonic'].values.T
        t = df['t'].values.T
        p = df['p'].values.T
        rh = df['rh'].values.T

        sampletimes += list(df.index) # append new timestamps
        tStop = len(sampletimes)
        tStrt = tStop - 3600*sampleRateRaw
        print("tStrt,tStop = {:d},{:d}".format(tStrt,tStop))
        outputtimes = sampletimes[tStrt:tStop:sampleStride]

        # original code written for height-time arrays instead of height-time
        assert u.shape == (Nz,signalRawSamples)

        # unit conversions on temperature(F->K) and pressure( 1 kPa to 10 mbars)
        t = (t - 32.)*5./9. + 273.15
        p = 10.*p
        R = 287.04
        cv = 718.0
        cp = R+cv
        R_cp = R/cp
        gamma = cp/cv
        p00 = 1.0e5 #(Pa)
        th = t * (p00 / (100.0*p))**R_cp

        ### As of 4_15_19 JAS added Branko form of tilt correction from EOL description
        u,v,w = tilt_correction(u.T,v.T,w.T,reg_coefs,tilts)
        # - note: the remainder of this function assumes arrays have dimensions (height,time)
        u = u.T
        v = v.T
        w = w.T

        # TODO: replace all of this 'subSampleByMean' code with # df.rolling().mean()
        if(subSampleByMean):# {{{
            ufRaw = np.zeros((Nz,sampleStride))
            vfRaw = np.zeros((Nz,sampleStride))
            wfRaw = np.zeros((Nz,sampleStride))
            tfRaw = np.zeros((Nz,sampleStride))
            thfRaw = np.zeros((Nz,sampleStride))
            pfRaw = np.zeros((Nz,sampleStride))
            i=0
            j=0
            for k in range(signalRawSamples):  #For each line in the file
                if (k%sampleStride == 0 and k > 0) or k == signalRawSamples-1:#Take the mean of the raw data over this sampleStride then compute fluctuations
                    #Compute the means
                    um[:,i] = np.nanmean(u[:,k-sampleStride:k],axis=1)
                    vm[:,i] = np.nanmean(v[:,k-sampleStride:k],axis=1)
                    wm[:,i] = np.nanmean(w[:,k-sampleStride:k],axis=1)
                    usm[:,i] = np.nanmean(us[:,k-sampleStride:k],axis=1)
                    vcm[:,i] = np.nanmean(vc[:,k-sampleStride:k],axis=1)
                    wdm[:,i] = np.nanmean(wd[:,k-sampleStride:k],axis=1)
                    tsm[:,i] = np.nanmean(ts[:,k-sampleStride:k],axis=1)
                    tm[:,i] = np.nanmean(t[:,k-sampleStride:k],axis=1)
                    thm[:,i] = np.nanmean(th[:,k-sampleStride:k],axis=1)
                    pm[:,i] = np.nanmean(p[:,k-sampleStride:k],axis=1)
                    rhm[:,i] = np.nanmean(rh[:,k-sampleStride:k],axis=1)
                    #Compute the core variable fluctuations 
                    for l in range(Nz):
                        ufRaw[l,:] = np.subtract(u[l,k-sampleStride:k],um[l,i])
                        vfRaw[l,:] = np.subtract(v[l,k-sampleStride:k],vm[l,i])
                        wfRaw[l,:] = np.subtract(w[l,k-sampleStride:k],wm[l,i])
                        tfRaw[l,:] = np.subtract(t[l,k-sampleStride:k],tm[l,i])
                        thfRaw[l,:] = np.subtract(t[l,k-sampleStride:k],thm[l,i])
                        pfRaw[l,:] = np.subtract(p[l,k-sampleStride:k],pm[l,i])
                    uf[:,i] = np.nanmean(ufRaw,axis=1)
                    vf[:,i] = np.nanmean(vfRaw,axis=1)
                    wf[:,i] = np.nanmean(wfRaw,axis=1)
                    tf[:,i] = np.nanmean(tfRaw,axis=1)
                    thf[:,i] = np.nanmean(thfRaw,axis=1)
                    pf[:,i] = np.nanmean(pfRaw,axis=1)
                    #Compute the auxilliary fluctuation products
                    tkem[:,i] = np.nanmean(np.multiply(ufRaw,ufRaw)+np.multiply(vfRaw,vfRaw)+np.multiply(wfRaw,wfRaw),axis=1)
                    tau11[:,i] = np.nanmean(np.multiply(ufRaw,ufRaw),axis=1)
                    tau12[:,i] = np.nanmean(np.multiply(ufRaw,vfRaw),axis=1)
                    tau13[:,i] = np.nanmean(np.multiply(ufRaw,wfRaw),axis=1)
                    tau23[:,i] = np.nanmean(np.multiply(vfRaw,wfRaw),axis=1)
                    tau22[:,i] = np.nanmean(np.multiply(vfRaw,vfRaw),axis=1)
                    tau33[:,i] = np.nanmean(np.multiply(wfRaw,wfRaw),axis=1)
                    hflux[:,i] = np.nanmean(np.multiply(thfRaw,wfRaw),axis=1)
                    #increment the target sample counter and reset the subfilter counter
                    i = i + 1
                    j = 0
                else:
                    j = j + 1# }}}

        # To match output intervals in original code
        # e.g., for N=180000, indices=[50,100,150,...,179900,179950,179999]
        #selected = slice(sampleStride,signalRawSamples,sampleStride)# {{{
        #um[:,:-1] = u[:,selected]
        #vm[:,:-1] = v[:,selected]
        #wm[:,:-1] = w[:,selected]
        #usm[:,:-1] = us[:,selected]
        #vcm[:,:-1] = vc[:,selected]
        #wdm[:,:-1] = wd[:,selected]
        #tsm[:,:-1] = ts[:,selected]
        #tm[:,:-1] = t[:,selected]
        #thm[:,:-1] = th[:,selected]
        #pm[:,:-1] = p[:,selected]
        #rhm[:,:-1] = rh[:,selected]
        #um[:,-1] = u[:,-1]
        #vm[:,-1] = v[:,-1]
        #wm[:,-1] = w[:,-1]
        #usm[:,-1] = us[:,-1]
        #vcm[:,-1] = vc[:,-1]
        #wdm[:,-1] = wd[:,-1]
        #tsm[:,-1] = ts[:,-1]
        #tm[:,-1] = t[:,-1]
        #thm[:,-1] = th[:,-1]
        #pm[:,-1] = p[:,-1]
        #rhm[:,-1] = rh[:,-1]# }}}
        
        # 1-Hz output, but has a 980ms offset
        # indices=[49,99,149,...,179999]
        #selected = slice(sampleStride-1,signalRawSamples,sampleStride)

        # 1-Hz output
        # indices=[0,50,100,...,179900,179950]
        # TODO: resample with pd.resample() to guarantee sampling consistency
        selected = slice(0,signalRawSamples,sampleStride)
        um[:,:] = u[:,selected]
        vm[:,:] = v[:,selected]
        wm[:,:] = w[:,selected]
        usm[:,:] = us[:,selected]
        vcm[:,:] = vc[:,selected]
        wdm[:,:] = wd[:,selected]
        tsm[:,:] = ts[:,selected]
        tm[:,:] = t[:,selected]
        thm[:,:] = th[:,selected]
        pm[:,:] = p[:,selected]
        rhm[:,:] = rh[:,selected]

        #
        # now, write all the data
        #
        for i in range(um.shape[1]):
            # write record header
            fout.write(record.format(
                date=dateStr,
                time=outputtimes[i].strftime(' %H:%M:%S'),
                ustar=0.25607,
                z0=0.1,
                T0=dummyval,
                qwall=dummyval,
            ))
            for allcols in zip(z,um[:,i],vm[:,i],wm[:,i],thm[:,i],pm[:,i],
                               tkem[:,i], tau11[:,i], tau12[:,i], tau13[:,i],
                               tau22[:,i], tau23[:,i], tau33[:,i], hflux[:,i]
                              ):
                # write data row
                fout.write(datarow.format(*allcols))

    fout.close()
    print("Done!")


#==============================================================================
if __name__ == '__main__':
    import sys
    if not len(sys.argv) == 4:
        sys.exit('USAGE: {:s} rawdatadir startdate outpath'.format(sys.argv[0]))
    inpath, startdate, outpath = sys.argv[1:]

    TTURawToMMC(inpath,startdate,outpath)

