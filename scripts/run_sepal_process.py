import time
import subprocess
import glob
import os
import ee
import sys
sys.path.append("..") # Adds higher directory to python modules path
from utils import utils
from scripts import gdrive
from threading import Thread

#initialize earth engine
ee.Initialize()

#Message
START_SEPAL = "the process has been launch on your SEPAL account"
NO_TASK = "The GEE process has not been completed, launch it or run a status check through step 2."
ALREADY_DONE = "This computation has already been performed\nYou can find your results in the glad_result folder of your computer"
COMPUTAION_COMPLETED = "Computation complete"

#function 
def merge(filename, alert_map, glad_dir):
    """ merge into a single tif files
    
    Args:
        filename (str): filename pattern of the Tif to merge
        alert_map (str): output filename
        glad_dir (tr): glad result folder
        
    Returns:
        process.stdout (str): output of the process
    """
    
    #create command
    command = [
        'gdal_merge.py',
        '-o', alert_map,
        '-v', '-co', '"COMPRESS=LZW"'
    ]
    #add the input files
    for file in glob.glob(glad_dir + filename):
        command.append(file)

    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    ) 
    
    return process.stdout
    
def clump(alert_map, clump_map):
    """ clump the results
    
    Args:
        alert_map (str): pathname to the alert tif file
        clump_map (str): pathname to the tmp clump file
    
    Returns:
        process.stdout (str): output of the process
    """
    
    process = subprocess.run(
        [
            'oft-clump', 
            '-i', alert_map, 
            '-o', clump_map
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    return process.stdout
    
def calc(clump_map, alert_map, alert_stats):
    """Compute the statistics per each individual clump
    
    Args:
        clump_map (str): pathname to the clump tif file
        alert_map (str): pathname to the alerts tif file
        alert_stat (str): pathname to the output path
        
    Results:
        process.stdout (str): output of the process
    """
    process = subprocess.run(
        [
            'oft-his', 
            '-um', clump_map, 
            '-i', alert_map, 
            '-o', alert_stats,
            '-maxval','3'
        
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    return(process.stdout)  


def download_task_tif(filename, glad_dir):
    """Download the tif files from your google drive folder to the local glad_results folder
    
    Args:
        filename (str): pathname pattern to the .tif files
        glad_dir (str): pathname to the local gad_result directory
    """
    drive_handler = gdrive.gdrive()
    files = drive_handler.get_files(filename)
    drive_handler.download_files(files, glad_dir)
    
def delete_local_file(pathname):
    """delete the files that have been already merged
    
    Args:
        pathnamec (str): the pathname patern to the .tif files 
        
    Returns: 
        (str): a message corresponding to the number of deleted files
    """
    #list the input files
    file_list = []
    for file in glob.glob(pathname):
        file_list.append(file)
        
    count = 0
    for file in file_list:
        os.remove(file)
        count += 1
        
    return "{0} files deleted".format(count)

def check_for_stats(filename):
    """return the file corresponding to the pathname else False
    
    Args:
        filename (str): expected pathname of the file
      
    Returns:
        (str) : the pathname if found else False
    """
    return glob.glob(filename)


def run_sepal_process(asset_name, year, widget_alert):
    """execute the 3 different operations of the computation successively: merg, clump and compute
    
    Args:
        asset_name (str): the assetId of the aoi computed in step 1
        year (str): the year used to compute the glad alerts
        widget_alert (v.Alert) the alert that display the output of the process
        
    Returns:
        (str,str): the links to the .tif (res. .txt) file 
    """
    
    aoi_name= utils.set_aoi_name(asset_name)
        
    #define the files variables
    glad_dir = utils.create_result_folder()
    
    #year and country_code are defined by step 1 cell
    alert_map   = glad_dir + "glad_" +year + "_" + aoi_name + ".tif"
    clump_map   = glad_dir + "tmp_clump_" + year + "_" + aoi_name + ".tif"
    alert_stats = glad_dir + "stats_glad_" + year + "_" + aoi_name + ".txt"
        
    filename = utils.construct_filename(asset_name, year)
    #check that the Gee process is finished
    if not utils.search_task(filename):
        utils.displayIO(widget_alert, 'error', NO_TASK)
        return ('#', '#')
        
    #check that the process is not already done
    if check_for_stats(alert_stats):
        utils.displayIO(widget_alert, 'success', ALREADY_DONE)
        return (create_download_link(alert_map), create_download_link(alert_stats))
    
    #download from GEE
    download_task_tif(filename, glad_dir)
        
    #process data with otf
    pathname = utils.construct_filename(asset_name, year) + "*.tif"
    
    t_merge = Thread(target=merge, args=(pathname, alert_map, glad_dir))
    utils.displayIO(widget_alert, 'info', 'starting merging')
    time.sleep(2)
    t_merge.start()
    while t_merge.is_alive():
        utils.displayIO(widget_alert, 'info', 'status: MERGE RUNNING')
    utils.displayIO(widget_alert, 'info', 'status: MERGE COMPLETED')
        
    time.sleep(2)
            
    io = delete_local_file(glad_dir + pathname)
    utils.displayIO(widget_alert, 'info', io)
        
    time.sleep(2)
            
    t_clump = Thread(target=clump, args=(alert_map, clump_map))
    utils.displayIO(widget_alert, 'info', 'starting clumping')
    time.sleep(2)
    t_clump.start()
    while t_clump.is_alive():
        utils.displayIO(widget_alert, 'info', 'status: CLUMPING RUNNING')
    utils.displayIO(widget_alert, 'info', 'status: CLUMPING COMPLETED')
        
    time.sleep(2)
            
    t_calc = Thread(target=calc, args=(clump_map, alert_map, alert_stats))
    utils.displayIO(widget_alert, 'info', 'starting computation')
    time.sleep(2)
    t_calc.start()
    while t_calc.is_alive():
        utils.displayIO(widget_alert, 'info', 'status: COMPUTATION RUNNING')
    utils.displayIO(widget_alert, 'info', 'status: COMPUTATION COMPLETED')
        
    time.sleep(2)
    
    io = delete_local_file(clump_map)
    utils.displayIO(widget_alert, 'info', io)
    
    time.sleep(2)
    
    utils.displayIO(widget_alert, 'success', COMPUTAION_COMPLETED)
    
    return (create_download_link(alert_map), create_download_link(alert_stats))
    
def create_download_link(pathname):
    result_path = os.path.expanduser(pathname)
    home_path = os.path.expanduser('~')
    download_path='/'+os.path.relpath(result_path,home_path)
    
    link = "/api/files/download?path={}".format(download_path)
    
    return link