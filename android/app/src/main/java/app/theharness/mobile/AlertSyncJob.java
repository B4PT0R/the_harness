package app.theharness.mobile;

import android.app.job.JobParameters;
import android.app.job.JobService;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

/** OS-controlled best-effort sync, not an always-connected push receiver. */
public final class AlertSyncJob extends JobService {
    private final ExecutorService network = Executors.newSingleThreadExecutor();
    private final java.util.Map<JobParameters, Future<?>> work = new java.util.HashMap<>();
    @Override public boolean onStartJob(JobParameters parameters) {
        work.put(parameters, network.submit(() -> { NativeAlerts.get(this).sync();
            new android.os.Handler(getMainLooper()).post(() -> { if (work.remove(parameters) != null) jobFinished(parameters, false); });
        }));
        return true;
    }
    @Override public boolean onStopJob(JobParameters parameters) {
        Future<?> stopped = work.remove(parameters); if (stopped != null) stopped.cancel(true); return true;
    }
    @Override public void onDestroy() { network.shutdownNow(); super.onDestroy(); }
}
