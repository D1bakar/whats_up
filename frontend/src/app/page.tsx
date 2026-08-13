import { getApiBaseUrl } from "@/lib/api";

export default function HomePage() {
  const apiBaseUrl = getApiBaseUrl();

  return (
    <main className="shell">
      <section className="card">
        <p className="eyebrow">Phase 0 foundation</p>
        <h1>WhatsApp Platform Admin</h1>
        <p>
          Application shell is ready. Dashboard features arrive in later phases.
        </p>
        <dl>
          <div>
            <dt>API base URL</dt>
            <dd>{apiBaseUrl}</dd>
          </div>
          <div>
            <dt>Health check</dt>
            <dd>
              <code>{apiBaseUrl}/health</code>
            </dd>
          </div>
        </dl>
      </section>
    </main>
  );
}
