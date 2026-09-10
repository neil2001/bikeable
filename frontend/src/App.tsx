import { useEffect, useState } from "react";
import { getCities, getHealth, isMockApi } from "./api/client";
import { ApiClientError } from "./api/errors";
import type { CitySummary, HealthResponse } from "./types/api";
import "./App.css";

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [cities, setCities] = useState<CitySummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [healthResponse, cityResponse] = await Promise.all([
          getHealth(),
          getCities(),
        ]);
        if (!cancelled) {
          setHealth(healthResponse);
          setCities(cityResponse.cities);
        }
      } catch (cause) {
        if (cancelled) {
          return;
        }
        if (cause instanceof ApiClientError) {
          setError(`${cause.code}: ${cause.message}`);
          return;
        }
        setError("Unable to reach the API.");
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="shell">
      <h1>Bikeable</h1>
      <p className="lede">
        Map-first cycling planner. API mode: {isMockApi() ? "mock" : "live"}.
      </p>
      {error ? <p className="error">{error}</p> : null}
      <dl>
        <dt>Health</dt>
        <dd>{health?.status ?? "loading…"}</dd>
        <dt>Cities</dt>
        <dd>
          {cities.length
            ? cities.map((city) => city.name).join(", ")
            : "loading…"}
        </dd>
      </dl>
    </main>
  );
}

export default App;
