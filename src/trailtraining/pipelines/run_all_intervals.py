from trailtraining.pipelines.run_all import main as run_all_main


def main(*, clean: bool = False, clean_processing: bool = False, clean_prompting: bool = False) -> None:
    """
    Back-compat wrapper: Run full pipeline (Intervals → Strava → Combine).

    By default we DO NOT wipe processing/ so Strava incremental state is preserved.
    """
    run_all_main(
        clean=clean,
        clean_processing=clean_processing,
        clean_prompting=clean_prompting,
        wellness_provider="intervals",
    )


if __name__ == "__main__":
    main()