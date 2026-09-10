import { Link } from 'react-router-dom'

const LAST_UPDATED = 'September 10, 2026'

interface SectionProps {
  title: string
  children: React.ReactNode
}

function Section({ title, children }: SectionProps) {
  return (
    <section className="mt-8">
      <h2 className="text-lg font-semibold text-white">{title}</h2>
      <div className="mt-3 space-y-3 text-sm leading-relaxed text-white/60">{children}</div>
    </section>
  )
}

const PrivacyPolicyPage = () => {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
      <p className="text-xs font-medium uppercase tracking-[0.25em] text-indigo-300/70">Legal</p>
      <h1 className="mt-2 text-3xl font-bold text-white sm:text-4xl">Privacy Policy</h1>
      <p className="mt-2 text-sm text-white/40">Last updated: {LAST_UPDATED}</p>

      <p className="mt-6 text-sm leading-relaxed text-white/60">
        This Privacy Policy explains how AI Virtual Office (&quot;AI Office&quot;, &quot;we&quot;) accesses, uses,
        stores, processes, and deletes data when you connect third-party services — such as Gmail,
        Google Drive, Telegram, Telegram Bot, and Discord — to the platform and let AI agents act
        on your behalf.
      </p>

      <Section title="1. Information We Collect">
        <p>
          <strong className="text-white/80">Account information.</strong> When you sign in with Google,
          we receive and store your Google account identifier, email address, display name, and profile
          picture URL.
        </p>
        <p>
          <strong className="text-white/80">Connected service data.</strong> When you connect an integration,
          we store the credentials required to operate it and process the content needed for your agents
          to work:
        </p>
        <ul className="list-disc space-y-1.5 pl-5">
          <li><strong className="text-white/80">Gmail:</strong> message headers, subject lines, snippets, and body text of emails the platform monitors (e.g. unread inbox mail), plus message IDs used for deduplication.</li>
          <li><strong className="text-white/80">Google Drive:</strong> file names, metadata, and the content of files your agents explicitly create or read at your request.</li>
          <li><strong className="text-white/80">Telegram Bot:</strong> message text, sender names/IDs, and chat identifiers for chats in which your bot participates.</li>
          <li><strong className="text-white/80">Telegram Account:</strong> message text and chat metadata for dialogs the connected account monitors.</li>
          <li><strong className="text-white/80">Discord:</strong> message text, author names/IDs, and channel identifiers for DM channels and server channels where your bot is a member.</li>
        </ul>
        <p>
          <strong className="text-white/80">Knowledge content.</strong> Text you submit to the knowledge base
          is split into chunks and converted into vector embeddings for semantic search.
        </p>
        <p>
          <strong className="text-white/80">Operational logs.</strong> We record agent actions (tool executions,
          decisions, approval events) in audit logs, and standard technical logs such as request IDs and timestamps.
        </p>
      </Section>

      <Section title="2. Credentials & Access to Your Services">
        <p>
          Access to Gmail, Drive, Calendar, Telegram, and Discord is granted by you through OAuth consent
          or API credentials that you provide. OAuth tokens and API keys are stored <strong className="text-white/80">encrypted
          at rest</strong> using symmetric encryption and are decrypted only in memory when a monitor or an
          agent action needs them. Credentials are never returned to the browser in plaintext and are never logged.
        </p>
        <p>
          The platform requests only the scopes needed for the features you enable (for example Gmail read/send,
          Drive file scope, Telegram bot messaging). You can revoke access at any time — either from the
          provider&apos;s own security settings or by disconnecting the integration in AI Office.
        </p>
      </Section>

      <Section title="3. How AI Agents Process Your Data">
        <p>
          When a message or event arrives (an email, a Telegram/Discord message, a scheduled run, or a chat
          instruction from you), the platform assembles a task context — the message content, relevant
          knowledge-base excerpts, and your agent&apos;s instructions — and sends it to the configured
          <strong className="text-white/80"> large language model (LLM) provider</strong> to produce a decision
          or a draft reply.
        </p>
        <p>
          This means message content and knowledge excerpts are transmitted to your configured LLM provider
          (for example OpenAI or an OpenRouter model) and processed under that provider&apos;s terms and privacy
          policy. Tool outputs (such as Drive file listings or email searches) may also be included in this
          processing step.
        </p>
        <p>
          Replies and actions that are classified as sensitive — including automated-looking messages and
          high-risk tool actions — are held in an approval queue and are not sent until you approve them.
        </p>
      </Section>

      <Section title="4. Data Storage & Security">
        <p>
          Data is stored in a PostgreSQL database you configure. The platform encrypts integration credentials
          with Fernet symmetric encryption, uses JWT-based authentication for dashboard access, rate-limits API
          traffic, and records an audit trail of agent tool executions. Access to the dashboard is protected by
          your Google sign-in.
        </p>
        <p>
          Because AI Office is self-hosted (or deployed to infrastructure you control), the primary custodian
          of the database — and therefore of your data — is you or your hosting provider.
        </p>
      </Section>

      <Section title="5. Data Retention & Deletion">
        <ul className="list-disc space-y-1.5 pl-5">
          <li><strong className="text-white/80">Disconnecting an integration</strong> immediately removes the stored credentials for that account from the platform. Content already processed (for example stored emails) remains until you delete it or delete the related records.</li>
          <li><strong className="text-white/80">Deleting a knowledge source</strong> removes its text and vector embeddings.</li>
          <li><strong className="text-white/80">Deleting an agent</strong> removes the agent, its triggers, and its execution history.</li>
          <li><strong className="text-white/80">Full account deletion</strong> can be requested by deleting your workspace data through the dashboard; residual copies may persist in encrypted database backups for a limited period.</li>
        </ul>
        <p>
          Disconnecting a service in the provider&apos;s own settings (Google security page, Telegram, Discord)
          revokes the underlying access independently of AI Office.
        </p>
      </Section>

      <Section title="6. Third-Party Services">
        <p>
          Your use of connected services is additionally governed by the respective provider&apos;s terms and
          privacy policies — Google (Gmail, Drive, Calendar), Telegram, Discord, and your LLM provider. AI Office
          acts on your behalf within the access you granted and does not sell your data to anyone.
        </p>
      </Section>

      <Section title="7. Changes to This Policy">
        <p>
          We may update this Privacy Policy as the platform evolves. Material changes will be reflected by the
          &quot;Last updated&quot; date above. Continued use of the service after changes take effect constitutes
          acceptance of the updated policy.
        </p>
      </Section>

      <Section title="8. Contact">
        <p>
          Questions about this policy? Reach out through the repository&apos;s issue tracker or your workspace
          administrator.
        </p>
      </Section>

      <div className="mt-12 flex gap-6 border-t border-white/10 pt-6 text-sm">
        <Link to="/terms" className="text-indigo-400 hover:text-indigo-300">Terms of Service →</Link>
        <Link to="/" className="text-white/50 hover:text-white">← Back to Home</Link>
      </div>
    </div>
  )
}

export default PrivacyPolicyPage
