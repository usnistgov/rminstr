if [ $# -eq 0 ]
then
    set -e
	echo "No arguments supplied, running tests"
    uv run ruff check
    uv run pytest tests --cov=rminstr tests/ src/  --junitxml=tests/report.xml --cov-report html --cov-report term  --doctest-modules
elif [ $1 = "open" ]
then
    set -e
    start htmlcov/index.html
fi
exit 0