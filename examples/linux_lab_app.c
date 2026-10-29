#define _POSIX_C_SOURCE 200809L
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/prctl.h>
#include <time.h>
#include <unistd.h>

#ifndef LAB_VERSION
#define LAB_VERSION "development"
#endif

static volatile sig_atomic_t stalled = 0;
static volatile sig_atomic_t stopping = 0;

static void handle_signal(int signal_number) {
    if (signal_number == SIGUSR1) stalled = 1;
    if (signal_number == SIGUSR2) stalled = 0;
    if (signal_number == SIGTERM) stopping = 1;
}

static void status(const char *state, unsigned long heartbeat) {
    FILE *file = fopen("status.tmp", "w");
    if (!file) { perror("status.tmp"); stopping = 1; return; }
    fprintf(file, "version=%s pid=%ld state=%s heartbeat=%lu\n",
            LAB_VERSION, (long)getpid(), state, heartbeat);
    if (fclose(file) || rename("status.tmp", "status.txt")) {
        perror("status.txt"); stopping = 1;
    }
}

/* Deliberate fixture failure: a blocked worker that a stack snapshot can identify. */
static void wait_for_recovery(void) {
    sigset_t block, previous;
    sigemptyset(&block);
    sigaddset(&block, SIGUSR2);
    sigaddset(&block, SIGTERM);
    sigprocmask(SIG_BLOCK, &block, &previous);
    while (stalled && !stopping) sigsuspend(&previous);
    sigprocmask(SIG_SETMASK, &previous, NULL);
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        puts(LAB_VERSION);
        return 0;
    }
    struct sigaction action = {0};
    action.sa_handler = handle_signal;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGUSR1, &action, NULL) || sigaction(SIGUSR2, &action, NULL) ||
        sigaction(SIGTERM, &action, NULL)) { perror("sigaction"); return 1; }
    /* Permit a sibling GDB only in this disposable, non-privileged example. */
    if (prctl(PR_SET_PTRACER, PR_SET_PTRACER_ANY, 0, 0, 0)) { perror("ptracer"); return 1; }
    setvbuf(stdout, NULL, _IOLBF, 0);
    printf("started version=%s pid=%ld\n", LAB_VERSION, (long)getpid());
    unsigned long heartbeat = 0;
    while (!stopping) {
        if (stalled) {
            puts("worker stalled: waiting for recovery input");
            status("stalled", heartbeat);
            wait_for_recovery();
            if (!stopping) puts("worker recovered");
        }
        if (!stopping) status("running", ++heartbeat);
        struct timespec interval = {0, 100000000};
        nanosleep(&interval, NULL);
    }
    puts("stopped");
    return 0;
}
