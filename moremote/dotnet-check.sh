#!/usr/bin/env bash
# Build and run every .NET project in moremote/, the way the image builds do.
#
# WHY THIS EXISTS
#
# The agent's C# is compiled in FIVE places with FIVE different file lists: the Linux agent, the
# Windows agent, and three test executables that each pull in a hand-written subset of the shared
# `agent/Core` and `agent/Web` sources. Adding one shared file and wiring it into some of those
# lists compiles perfectly — until the one that was missed.
#
# That is not hypothetical. `Core/HostBudget.cs` was added, wired into the Linux agent and
# MoRemote.Tests, both built clean locally, and the ARM image build then died at
#
#     /src/agent/Web/StreamSession.cs(200,22): error CS0103:
#         The name 'HostBudget' does not exist in the current context
#         [/src/tests/MoRemote.Stream.Tests/MoRemote.Stream.Tests.csproj]
#
# after twenty-five minutes of image build, because MoRemote.Stream.Tests compiles StreamSession.cs
# and had not been given the new file. The fast x86 job that runs these three executables in about
# a minute exists — and `build.yml` only triggers on pushes to `main`, so on a branch it does not
# run at all. The only pre-merge signal was the 180-minute ARM build.
#
# So: run this before pushing anything under moremote/. It needs the dotnet SDK and nothing else.
#
#     bash moremote/dotnet-check.sh        # or: just dotnet-check
#
# tests/test_dotnet_project_coverage.py fails the build if a .csproj appears in the tree and not
# here, so a new project cannot quietly go unbuilt.
set -euo pipefail

cd "$(dirname "$0")"

# The three the image builds RUN (they are executables that assert and exit non-zero).
run=(
    tests/MoRemote.Tests
    tests/MoRemote.Linux.Input.Tests
    tests/MoRemote.Stream.Tests
    tests/MoRemote.Windows.Power.Tests
)
# The two the image builds only COMPILE. VisualInputTest injects real input into a live session
# and is deliberately never run unattended — building it still catches a broken shared header.
build=(
    agent-linux/MoRemoteLinux.csproj
    agent/MoRemoteAgent.csproj
    tests/VisualInputTest
)

# The Windows agent targets net10.0-windows, which CI compiles on a windows-latest runner. From
# Linux the SDK needs EnableWindowsTargeting to pull the Windows reference assemblies; that gives
# the COMPILE signal (which is the one that matters here — WebApi and StreamSession are shared
# with the Linux agent, and a shared file missing from this project's list breaks it) without
# pretending the result is runnable.
for project in "${build[@]}"; do
    echo "── build $project"
    dotnet build "$project" -c Release -v q --nologo -p:EnableWindowsTargeting=true
done
for project in "${run[@]}"; do
    echo "── run   $project"
    dotnet run --project "$project" -c Release --nologo
done
echo "PASS: every moremote .NET project compiles, and every test executable passed"
