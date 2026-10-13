"""Run trusted fixture benchmarks or an explicitly configured, budgeted model study."""
import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fault', choices=['none','transient','timeout_after_commit'], default='none')
    parser.add_argument('--repetitions', type=int, default=2)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--database', help='Optional separate SQLite database for experiment records')
    parser.add_argument('--study-manifest', help='Version-two study JSON; model mode requires explicit pilot budgets')
    parser.add_argument('--resume', help='Resume the same persisted experiment without resetting its budgets')
    parser.add_argument('--output', required=True, help='JSON report destination')
    args = parser.parse_args()
    if args.database:
        database = Path(args.database).resolve()
        database.parent.mkdir(parents=True, exist_ok=True)
        os.environ['AGENTEVAL_DB_PATH'] = str(database)
    from .models.benchmark import ExperimentManifest
    from .services.benchmark_service import benchmark_service
    if args.study_manifest:
        from .models.benchmark_study import StudyManifest
        from .services.benchmark_study_service import study_service
        manifest = StudyManifest.model_validate_json(Path(args.study_manifest).read_text(encoding='utf-8'))
        report = study_service.run(manifest, args.resume)
    else:
        report = benchmark_service.run(ExperimentManifest(repetitions=args.repetitions, seed=args.seed, fault={'kind':args.fault}), args.resume)
    destination = Path(args.output).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"{len(report['trials'])} trial records. Experiment status: {report['status']}. Report: {destination}")


if __name__ == '__main__':
    main()
