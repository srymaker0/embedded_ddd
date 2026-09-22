#include <signal.h>
#include <stdio.h>
#include <sys/prctl.h>
#include <time.h>

static volatile sig_atomic_t running = 1;
static void stop(int signal_number) { (void)signal_number; running = 0; }

int main(void) {
    /* Only this disposable fixture permits sibling GDB attachment under Yama. */
    if (prctl(PR_SET_PTRACER, PR_SET_PTRACER_ANY, 0, 0, 0) != 0) return 2;
    signal(SIGTERM, stop);
    puts("ready");
    fflush(stdout);
    const struct timespec delay = {0, 10000000};
    while (running) nanosleep(&delay, NULL);
    return 0;
}
