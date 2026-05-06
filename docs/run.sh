#!/usr/bin/env bash
# Run Sphinx for UNIX environments
#
function usage() {
	printf "usage: $0 [options] [MODE]\n"
	printf " options: $0 [-h|--help] [-n|--dry-run] [MODE]\n"
	printf "   -h|--help    : Print this message\n"
	printf "   -n|--dry-run : Print command, don't run it\n"
	printf " values for MODE:\n"
	printf "   changed : Only regenerate changed files [default]\n"
	printf "   all     : Regenerate all files\n"
	exit 0
}

mode="changed"
dryrun=0
while [ $# -gt 0 ]
do
	arg=$1
	case "$arg" in
		-h|--help) usage  ;;
		-n|--dry-run) dryrun=1 ;;
		changed) flags="" ;;
		all) flags="-nWa" ;;
		*) printf "Error: invalid argument '$arg'\n"; usage ;;
	esac
	shift
done

if [ $dryrun -eq 1 ]
then
	printf "sphinx-build $flags -w sphinx.out . build\n"
else
	sphinx-build $flags -w sphinx.out . build
fi
