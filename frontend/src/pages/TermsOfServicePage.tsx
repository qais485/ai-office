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

const TermsOfServicePage = () => {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
      <p className="text-xs font-medium uppercase tracking-[0.25em] text-indigo-300/70">Legal</p>
      <h1 className="mt-2 text-3xl font-bold text-white sm:text-4xl">Terms of Service</h1>
      <p className="mt-2 text-sm text-white/40">Last updated: {LAST_UPDATED}</p>

      <p className="mt-6 text-sm leading-relaxed text-white/60">
        These Terms of Service (&quot;Terms&quot;) govern your use of AI Virtual Office
        (&quot;AI Office&quot;, &quot;the Service&quot;) — a platform that lets you hire AI agents,
        connect third-party services such as Gmail, Google Drive, Telegram, Telegram Bot, and Discord,
        and automate work across them. By using the Service you agree to these Terms.
      </p>

      <Section title="1. The Service">
        <p>
          AI Office provides a dashboard in which you create office rooms, hire AI agents from templates,
          connect your own accounts on supported third-party services, and define knowledge and rules that
          guide those agents. Agents act on your behalf within the access you grant them.
        </p>
      </Section>

      <Section title="2. Accounts & Sign-In">
        <ul className="list-disc space-y-1.5 pl-5">
          <li>You must sign in with a valid Google account and keep your credentials secure.</li>
          <li>You are responsible for all activity that occurs under your account.</li>
          <li>One account per person; do not share dashboard access or API credentials with unauthorized parties.</li>
        </ul>
      </Section>

      <Section title="3. Connected Third-Party Accounts">
        <p>
          When you connect Gmail, Google Drive, Telegram, Discord, or any other service, you explicitly grant
          AI Office permission to access that service within the scopes you approve. You confirm that:
        </p>
        <ul className="list-disc space-y-1.5 pl-5">
          <li>the accounts you connect belong to you or that you are authorized to connect them;</li>
          <li>you will comply with the third-party provider&apos;s terms of service and acceptable-use policies;</li>
          <li>you may revoke access at any time, either from the provider&apos;s settings or by disconnecting the integration in AI Office — after which the platform stops accessing that service and deletes the stored credentials.</li>
        </ul>
        <p>
          AI Office is not affiliated with Google, Telegram, or Discord. Those providers may change or restrict
          their APIs at any time, which can affect the functionality of connected integrations.
        </p>
      </Section>

      <Section title="4. AI Agents & Automation">
        <ul className="list-disc space-y-1.5 pl-5">
          <li>Agents act <strong className="text-white/80">on your behalf and on your instructions</strong> — through templates you hire, rules you set, knowledge you provide, and messages you send them. You are responsible for the outcomes of instructions you give.</li>
          <li>Agents may automatically read inbound messages from connected channels, answer them using your knowledge base, and execute approved tool actions (such as sending replies or creating Drive files).</li>
          <li>Actions classified as sensitive are held in an approval queue until you approve them. You remain responsible for approving, rejecting, or editing them.</li>
          <li>AI-generated content can contain mistakes. Review important replies and files before they affect your customers or business.</li>
          <li>You must not instruct agents to violate laws, third-party terms, or the acceptable-use rules below.</li>
        </ul>
      </Section>

      <Section title="5. Acceptable Use">
        <p>You agree not to use the Service to:</p>
        <ul className="list-disc space-y-1.5 pl-5">
          <li>send spam, unsolicited bulk messages, or phishing content through any connected channel;</li>
          <li>harass, threaten, or mislead people, or impersonate others without disclosure;</li>
          <li>process unlawful, infringing, or malicious content, or attempt to compromise the platform or other users;</li>
          <li>exceed rate limits or deliberately circumvent the technical restrictions of third-party services;</li>
          <li>connect accounts you do not own or scrape data you have no right to access.</li>
        </ul>
        <p>
          We may suspend or terminate access for violations of these Terms.
        </p>
      </Section>

      <Section title="6. Third-Party Services">
        <p>
          Your use of Gmail, Drive, Calendar, Telegram, Discord, LLM providers, and any other connected service
          is subject to that provider&apos;s own terms and privacy policies. AI Office relies on public APIs those
          providers expose and does not guarantee their availability, accuracy, or continued operation.
        </p>
      </Section>

      <Section title="7. Availability & Changes">
        <p>
          The Service is provided as-is and may be modified, interrupted, or discontinued — in whole or in part —
          at any time. We may add, change, or remove features, templates, and integrations as the platform evolves.
        </p>
      </Section>

      <Section title="8. Disclaimer of Warranties">
        <p>
          THE SERVICE IS PROVIDED &quot;AS IS&quot; AND &quot;AS AVAILABLE&quot; WITHOUT WARRANTIES OF ANY KIND,
          EXPRESS OR IMPLIED, INCLUDING MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.
          WE DO NOT WARRANT THAT THE SERVICE WILL BE UNINTERRUPTED, ERROR-FREE, OR THAT AI-GENERATED OUTPUT WILL
          BE ACCURATE OR COMPLETE.
        </p>
      </Section>

      <Section title="9. Limitation of Liability">
        <p>
          TO THE MAXIMUM EXTENT PERMITTED BY LAW, AI OFFICE AND ITS OPERATORS SHALL NOT BE LIABLE FOR ANY
          INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES — INCLUDING LOST PROFITS, DATA LOSS,
          OR DAMAGE ARISING FROM MESSAGES SENT OR ACTIONS TAKEN BY AGENTS ON YOUR BEHALF — EVEN IF ADVISED OF
          THE POSSIBILITY OF SUCH DAMAGES.
        </p>
      </Section>

      <Section title="10. Termination">
        <p>
          You may stop using the Service and disconnect your integrations at any time. We may suspend or terminate
          your access if you breach these Terms or use the Service in a way that creates legal or security risk.
        </p>
      </Section>

      <Section title="11. Changes to These Terms">
        <p>
          We may update these Terms from time to time. The &quot;Last updated&quot; date above reflects the current
          version. Continued use of the Service after changes take effect constitutes acceptance of the updated Terms.
        </p>
      </Section>

      <Section title="12. Contact">
        <p>
          Questions about these Terms? Reach out through the repository&apos;s issue tracker or your workspace
          administrator.
        </p>
      </Section>

      <div className="mt-12 flex gap-6 border-t border-white/10 pt-6 text-sm">
        <Link to="/privacy" className="text-indigo-400 hover:text-indigo-300">Privacy Policy →</Link>
        <Link to="/" className="text-white/50 hover:text-white">← Back to Home</Link>
      </div>
    </div>
  )
}

export default TermsOfServicePage
