// SPDX-License-Identifier: GPL-2.0-or-later
// Native process ownership controls; built in the SDK, executed before image copy.
// All subprocesses are private to this executable. No desktop bus or hardware query.
#include "statusqueryprocess.h"

#include <QCoreApplication>
#include <QElapsedTimer>
#include <QPointer>
#include <QThread>

#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <sys/prctl.h>
#include <sys/wait.h>

namespace
{
void require(bool value, const char *message)
{
    if (!value)
        throw std::runtime_error(message);
}

// Become the orphan's reaper as well: a container's PID 1 need not reap it for us.
bool reap(pid_t pid, int milliseconds = 1500)
{
    QElapsedTimer deadline;
    deadline.start();
    do {
        int status = 0;
        if (::waitpid(pid, &status, WNOHANG) == pid)
            return true;
        QThread::msleep(10);
    } while (deadline.elapsed() < milliseconds);
    return false;
}

struct Helper
{
    QPointer<QProcess> owner;
    pid_t pid = 0;
    pid_t probe = 0;
    ~Helper()
    {
        // Cleanup only the exact owned fixture PIDs, including a broken implementation.
        if (owner && owner->state() != QProcess::NotRunning) {
            owner->kill();
            owner->waitForFinished(1000);
        }
        if (probe > 1) {
            ::kill(probe, SIGKILL);
            reap(probe);
        }
    }
    void start(QProcess &process)
    {
        owner = &process;
        process.start(QCoreApplication::applicationFilePath(), {QStringLiteral("--helper")});
        require(process.waitForStarted(2000), "private collector did not start");
        pid = static_cast<pid_t>(process.processId());
        require(process.waitForReadyRead(2000), "private probe did not become ready");
        probe = process.readLine().trimmed().toInt();
        require(probe > 1 && ::kill(probe, 0) == 0, "missing private probe PID");
    }
    void gone()
    {
        require(reap(probe), "read-only probe survived collector cancellation");
        probe = 0;
    }
};
}

int main(int argc, char **argv)
{
    QCoreApplication application(argc, argv);
    if (application.arguments().contains(QStringLiteral("--helper"))) {
        const pid_t child = ::fork();
        if (child < 0)
            return 2;
        if (child == 0) {
            for (;;)
                ::pause();
        }
        std::printf("%d\n", child);
        std::fflush(stdout);
        for (;;)
            ::pause();
    }
    if (application.arguments().contains(QStringLiteral("--reply"))) {
        std::puts("{\"schema\":1,\"ok\":true}");
        return 0;
    }
    if (::prctl(PR_SET_CHILD_SUBREAPER, 1) != 0)
        return 2;
    try {
        // A separately owned change must remain alive through every query cancellation.
        QProcess change;
        change.setUnixProcessParameters(QProcess::UnixProcessFlag::CreateNewSession);
        Helper independent;
        independent.start(change);
        const pid_t changePid = independent.pid;

        // Completed old behavior: killing only QProcess leaves its probe alive.
        {
            QProcess old;
            Helper helper;
            helper.start(old);
            old.kill();
            require(old.waitForFinished(1000), "old collector did not end");
            require(!reap(helper.probe, 100) && ::kill(helper.probe, 0) == 0,
                    "old negative did not reproduce the orphan");
            std::puts("old kill-only negative: orphan observed and privately retired");
        }
        for (int count = 0; count < 10; ++count) {
            MoOSStatusQuery query;
            Helper helper;
            helper.start(query);
            require(::getpgid(helper.pid) == helper.pid && ::getsid(helper.pid) == helper.pid,
                    "query does not own its session/group");
            require(::getpgid(helper.probe) == helper.pid, "probe escaped private query group");
            query.cancel();
            require(query.state() == QProcess::NotRunning, "collector remained running");
            helper.gone();
        }
        std::puts("explicit cancellation: 10 collectors and probes reaped");
        {
            Helper helper;
            {
                MoOSStatusQuery query;
                helper.start(query);
            }
            helper.gone();
        }
        std::puts("page destruction: collector and probe reaped");
        {
            MoOSStatusQuery query;
            query.start(QCoreApplication::applicationFilePath(), {QStringLiteral("--reply")});
            query.cancel();
            require(query.state() == QProcess::NotRunning, "startup cancellation failed");
        }
        {
            MoOSStatusQuery query;
            query.start(QCoreApplication::applicationFilePath(), {QStringLiteral("--reply")});
            require(query.waitForFinished(2000) && query.exitCode() == 0,
                    "ordinary status result did not complete");
            require(query.readAllStandardOutput().trimmed() == "{\"schema\":1,\"ok\":true}",
                    "ordinary status output was lost");
            query.cancel();
        }
        {
            MoOSStatusQuery query;
            query.start(QStringLiteral("/moos-query-check/absent-program"), {});
            require(!query.waitForStarted(1000), "failed-start control unexpectedly started");
            query.cancel();
        }
        require(::kill(changePid, 0) == 0 && ::kill(independent.probe, 0) == 0,
                "query cancellation reached the independent change");
        ::kill(-changePid, SIGKILL);
        require(change.waitForFinished(1000), "private change cleanup failed");
        independent.gone();
        std::puts("startup, normal output, failed start and independent change controls: pass");
        return 0;
    } catch (const std::exception &failure) {
        std::fprintf(stderr, "status-query lifetime failure: %s\n", failure.what());
        return 1;
    }
}
