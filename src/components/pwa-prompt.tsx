import { RefreshCw, X } from "lucide-react";
import { useRegisterSW } from "virtual:pwa-register/react";
import { Button } from "./ui";

export function PwaPrompt() {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    offlineReady: [offlineReady, setOfflineReady],
    updateServiceWorker,
  } = useRegisterSW();
  if (!needRefresh && !offlineReady) return null;
  return (
    <div className="pwa-prompt" role="status">
      <span>
        {needRefresh ? <RefreshCw /> : <span className="pwa-prompt__dot" />}
      </span>
      <div>
        <strong>
          {needRefresh
            ? "A ChapelFlow update is ready"
            : "ChapelFlow is ready offline"}
        </strong>
        <p>
          {needRefresh
            ? "Refresh when convenient to use the latest version."
            : "Previously visited pages can now open without a connection."}
        </p>
      </div>
      {needRefresh && (
        <Button onClick={() => void updateServiceWorker(true)}>Refresh</Button>
      )}
      <button
        className="icon-button"
        aria-label="Dismiss"
        onClick={() => {
          setNeedRefresh(false);
          setOfflineReady(false);
        }}
      >
        <X />
      </button>
    </div>
  );
}
