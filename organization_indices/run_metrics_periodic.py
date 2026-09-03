import numpy as np
from objects_periodic import *
import metrics_periodic
import matplotlib.pyplot as plt



def run_metrics_periodic (image) :
    
    image_size = image.size
    domain_length = image.shape[0]
    objects          = make_objects(image)   # class containing regions and polynoms
    pairs_of_objects = make_pairs(objects, domain_length, domain_length)   # class containing all pairs of objects


    dict_org = dict()
    dict_org['area']      = objects.area_skm
    dict_org['number']    = objects.number_of_objects

    dict_org['Iorg']      = metrics_periodic.Iorg(pairs_of_objects, image_size=image_size)
    dict_org['Lorg']      = metrics_periodic.Lorg(pairs_of_objects,  l_max=2.*image.shape[0],  domain_length=domain_length)


    dict_org['SCAI']      = - metrics_periodic.SCAI(pairs_of_objects, image_size=image_size)
    dict_org['MCAI']      = - metrics_periodic.MCAI(pairs_of_objects, image_size=image_size)

    dict_org['COP']       = metrics_periodic.COP(pairs_of_objects)
    dict_org['ABCOP']     = metrics_periodic.ABCOP(pairs_of_objects, image_size=image_size)
    dict_org['ROME']      = metrics_periodic.ROME(pairs_of_objects)
    # dict_org['MICA']      = metrics.MICA(pairs_of_objects, image_size=image_size)

    dict_org['OIDRA'] = metrics_periodic.OIDRA(pairs_of_objects, image_size=image_size)


    # derived variables with safe division
    if dict_org['number'] != 0:
        dict_org['mean_area'] = dict_org['area'] / dict_org['number']
    else:
        dict_org['mean_area'] = np.nan  # or other appropriate value, e.g., 0



    # set to NAN all the metrics when N=1 (23% of the events, 1.5% of the events for C2)
    if dict_org['number'] <= 1 :
        dict_org['Iorg']      = np.nan
        dict_org['Lorg']      = np.nan
        dict_org['SCAI']      = np.nan
        dict_org['MCAI']      = np.nan
        dict_org['COP']       = np.nan
        dict_org['ABCOP']     = np.nan
        dict_org['ROME']      = np.nan
        # dict_org['MICA']      = np.nan
        dict_org['OIDRA'] = np.nan






    # store to compare with anomalies and percentiles
    dict_org['area_original']      = dict_org['area']
    dict_org['number_original']    = dict_org['number']

    return dict_org
