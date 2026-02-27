import os
from trailtraining import config
from trailtraining.pipelines import intervals as intervals_pipeline
from trailtraining.pipelines import strava as strava_pipeline
from trailtraining.data import combine as combine_jsons

def main():
    os.makedirs(config.PROCESSING_DIRECTORY, exist_ok=True)
    os.makedirs(config.PROMPTING_DIRECTORY, exist_ok=True)

    # clear processing + prompting (same behavior as run-all)
    for directory in [config.PROCESSING_DIRECTORY, config.PROMPTING_DIRECTORY]:
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)

    intervals_pipeline.main()
    strava_pipeline.main()
    combine_jsons.main()
    print("All pipelines (Intervals + Strava) completed successfully.")
