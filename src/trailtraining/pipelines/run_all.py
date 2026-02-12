from trailtraining.pipelines import garmin as garmin_pipeline, download_garmin_data, strava as strava_pipeline
from trailtraining.data import combine as combine_jsons
import os
from trailtraining import config

# This script runs all pipelines in the correct order.
#then it runs a final function to combine the jsons in the prompting directory
import json
import re

from datetime import datetime


def main():
    #check if processing and prompting directories exist, if not create them
    os.makedirs(config.PROCESSING_DIRECTORY, exist_ok=True)
    os.makedirs(config.PROMPTING_DIRECTORY, exist_ok=True)
    #if they exist, clear them
    for directory in [config.PROCESSING_DIRECTORY, config.PROMPTING_DIRECTORY]:
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
    #set the garmin config
    download_garmin_data.write_config()
    #run the garmin pipeline
    garmin_pipeline.main()
    #run the strava pipeline
    strava_pipeline.main()
    #combine the jsons in the prompting directory
    combine_jsons.main()
    print("All pipelines completed successfully.")

if __name__ == "__main__":
    main()
