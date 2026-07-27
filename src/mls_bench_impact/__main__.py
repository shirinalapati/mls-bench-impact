from mls_bench_impact.pipeline import run_pipeline

if __name__ == "__main__":
    import json

    print(json.dumps(run_pipeline(), indent=2))