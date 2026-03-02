from trailtraining.pipelines import garmin as garmin_pipeline, download_garmin_data, strava as strava_pipeline
from trailtraining.data import combine as combine_jsons
import os
import shutil
from trailtraining import config


def _clean_directory(directory: str) -> None:
    if not os.path.isdir(directory):
        return
    for name in os.listdir(directory):
        p = os.path.join(directory, name)
        try:
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
        except FileNotFoundError:
            pass


def main(*, clean: bool = False, clean_processing: bool = False, clean_prompting: bool = False) -> None:
    """
    Run full pipeline (Garmin → Strava → Combine).

    IMPORTANT:
    - By default we DO NOT wipe processing/, so Strava incremental state (processing/strava_meta.json) is preserved.
    - Use clean / clean_processing to force a full Strava refetch.
    """
    config.ensure_directories()

    if clean:
        clean_processing = True
        clean_prompting = True

    if clean_processing:
        _clean_directory(config.PROCESSING_DIRECTORY)
    if clean_prompting:
        _clean_directory(config.PROMPTING_DIRECTORY)

    # set the garmin config
    download_garmin_data.write_config()
    # run the garmin pipeline
    garmin_pipeline.main()
    # run the strava pipeline (incremental if processing/strava_meta.json exists)
    strava_pipeline.main()
    # combine the jsons in the prompting directory
    combine_jsons.main()
    print("All pipelines completed successfully.")


if __name__ == "__main__":
    main()