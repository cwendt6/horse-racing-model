# Horse Racing Prediction Model (Keeneland)

A Python handicapping model for thoroughbred races at Keeneland. It parses past-performance PDFs, scores every horse on a set of weighted factors, converts scores to win probabilities, and flags bets where the model's probability beats the market's odds (positive expected value).

I built this as a side project to practice the same things I do in finance: messy data extraction, model building, backtesting, and being honest about whether a model actually works.

## How it works

1. **Parse.** `src/parsers/hybrid_parser_v3.py` extracts running lines, speed figures, fractional times, workouts, trainer and jockey data from past-performance PDFs. Equibase XML results are parsed for backtesting.
2. **Score.** Analyzers in `src/analyzers/` score each horse on speed, pace scenario, class, distance and surface fit, trainer and jockey patterns, equipment changes, workouts, and track bias.
3. **Price.** `src/core/probability_calculator.py` and `src/betting/probability_calibrator.py` normalize scores into win probabilities.
4. **Find value.** `src/betting/value_detector.py` compares model probability to morning-line odds and flags overlays. `src/betting/exotic_strategy.py` builds exacta and trifecta structures.
5. **Optimize and backtest.** `src/core/weight_optimizer.py` tunes factor weights with grid search and differential evolution. `src/core/backtesting_framework.py` scores predictions against actual results.

## Results

| Test | Races | Win rate (top pick) | Top-3 hit rate | Top-5 hit rate |
|---|---|---|---|---|
| Oct 2025 meet, weights tuned on this data (in-sample) | 64 | 28.1% | 73.4% | 81.3% |
| Oct 2023 meet, never seen by the model (out-of-sample) | 86 | 17.4% | 37.2% | 55.8% |

Random chance in a 9 to 10 horse field is about 10% to win.

**The takeaway:** the out-of-sample test beat random, but the drop from in-sample to out-of-sample showed the tuned weights were overfit. The full write-up is in [`docs/2023_KEENELAND_VALIDATION_REPORT.md`](docs/2023_KEENELAND_VALIDATION_REPORT.md). Next steps are fewer free parameters, walk-forward validation, and a larger multi-meet training set.

## Project structure

```
src/
  parsers/        PDF and XML parsers (hybrid_parser_v3 is the production parser)
  analyzers/      Factor scoring: pace, speed, class, trainer/jockey, bias, workouts
  core/           Probability calculation, weight optimizer, backtesting framework
  betting/        Probability calibration, value detection, exotic bet strategy
  optimization/   Model optimizer
  visualization/  Race dashboard
scripts/          Backtests, weight optimization, analysis, production prediction
config/           Optimized weight sets
historical/       2023 backtest scripts and earlier optimization runs
tests/            Parser and scoring tests
docs/             Backtest reports and parser documentation
```

## Running it

Try it on the synthetic demo card (no data files needed):

```bash
pip install -r requirements.txt
python scripts/production/predict_from_pdf.py --sample
```

With your own past-performance PDFs:

```bash
./run_prediction.sh "path/to/past_performances.pdf"      # all races
./run_prediction.sh "path/to/past_performances.pdf" 3    # one race
./run_validation.sh                                       # compare predictions to results
```

## Data

Past-performance PDFs and Equibase result files are licensed data and are **not included** in this repo. Bring your own files to run the model on real races.

`sample_data/` holds a synthetic card (fictional track, horses, jockeys and trainers) plus matching jockey and trainer stats. `scripts/make_sample_card.py` regenerates it. `config/` holds the tuned weights and the probability calibration from the October 2025 backtest (aggregates only).

## Tech

Python, pandas, NumPy, SciPy (differential evolution), scikit-learn, pdfplumber, matplotlib.

## Disclaimer

For research and educational purposes. Not betting advice.
