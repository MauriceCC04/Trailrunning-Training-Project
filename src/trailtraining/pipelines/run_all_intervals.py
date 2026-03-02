import os
import shutil
from trailtraining import config
from trailtraining.pipelines import intervals as intervals_pipeline
from trailtraining.pipelines import strava as strava_pipeline
from trailtraining.data import combine as combine_jsons


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
    Run full pipeline (Intervals → Strava → Combine).

    By default we DO NOT wipe processing/ so Strava incremental state is preserved.
    """
    config.ensure_directories()

    if clean:
        clean_processing = True
        clean_prompting = True

    if clean_processing:
        _clean_directory(config.PROCESSING_DIRECTORY)
    if clean_prompting:
        _clean_directory(config.PROMPTING_DIRECTORY)

    intervals_pipeline.main()
    strava_pipeline.main()
    combine_jsons.main()
    print("All pipelines (Intervals + Strava) completed successfully.")