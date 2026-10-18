// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <QProcess>

#include <csignal>
#include <unistd.h>

// Only the read-only status collector belongs here. Mutations have their own user
// units and must survive closing a page. Killing just this collector's Python PID
// leaves a pending bluetoothctl (or another probe) orphaned in the app cgroup.
class MoOSStatusQuery final : public QProcess
{
public:
    MoOSStatusQuery()
    {
        setUnixProcessParameters(QProcess::UnixProcessFlag::CreateNewSession);
        setStandardInputFile(QProcess::nullDevice());
    }

    ~MoOSStatusQuery() override
    {
        disconnect();
        cancel();
    }

    void cancel()
    {
        if (state() == QProcess::NotRunning)
            return;
        // Closing a page can race start(). Resolve the startup notification before
        // deciding whether setsid succeeded; never signal our inherited process group.
        if (state() == QProcess::Starting)
            waitForStarted(1000);
        const pid_t pid = static_cast<pid_t>(processId());
        if (pid > 1 && ::getpgid(pid) == pid && ::getsid(pid) == pid)
            ::kill(-pid, SIGKILL);
        else
            kill();
        waitForFinished(1000);
    }
};
