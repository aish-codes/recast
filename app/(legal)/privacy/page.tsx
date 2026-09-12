import type { Metadata } from "next";
import Link from "next/link";
import { Bullets, Lede, Section, Title } from "../parts";

export const metadata: Metadata = {
  title: "Privacy Policy · recast",
  description: "What Recast collects, why, and how long it keeps it.",
};

// Baseline text, written to match what the code actually does — Google sign-in
// for identity, Supabase for storage, a model provider for the rewriting step.
// It is a starting point and not legal advice; have it reviewed before this is
// offered to anyone outside the people who built it.
const UPDATED = "12 September 2026";

export default function Privacy() {
  return (
    <>
      <Title updated={UPDATED}>Privacy Policy</Title>

      <Lede>
        Recast handles your resume, which is about as personal as a document
        gets. This page says what we collect, why we need it, who else sees it,
        and how to get rid of it.
      </Lede>

      <Section n="01" title="What we collect">
        <p>
          <strong className="font-semibold text-ink">Your Google account details.</strong> When you
          sign in with Google we receive your name, email address and profile picture. We ask for
          nothing else, and we never receive your Google password.
        </p>
        <p>
          <strong className="font-semibold text-ink">What you upload.</strong> The resume you upload
          and the job descriptions you paste in, along with everything we derive from them: your
          master profile, each tailored resume, cover letters and match analyses.
        </p>
        <p>
          <strong className="font-semibold text-ink">The state of your applications.</strong> The
          status you set on each application, and any notes you add to it.
        </p>
      </Section>

      <Section n="02" title="Why we hold it">
        <Bullets
          items={[
            "To identify you, so your documents come back to you and to nobody else.",
            "To produce a tailored resume: the job description and your profile are what the pipeline reads.",
            "To show you your own history — the applications you have started and what happened to them.",
          ]}
        />
        <p>
          We do not sell your data, we do not share it with recruiters or employers, and we do not
          use it to advertise to you.
        </p>
      </Section>

      <Section n="03" title="Who else it reaches">
        <p>
          Three processors, each doing one job:
        </p>
        <Bullets
          items={[
            <>
              <strong className="font-semibold text-ink">Google</strong> — sign-in only. Google
              tells us who you are; we tell Google nothing about what you do here.
            </>,
            <>
              <strong className="font-semibold text-ink">Supabase</strong> — authentication and the
              database your documents are stored in.
            </>,
            <>
              <strong className="font-semibold text-ink">Groq</strong> — the model provider that
              performs the rewriting. The text of your profile and the job description is sent for
              each recast. It is not used to train models.
            </>,
          ]}
        />
      </Section>

      <Section n="04" title="How it is kept">
        <p>
          Your rows are keyed to your account id, and every query the application makes is scoped to
          it. The database additionally enforces row-level security, so a request that somehow
          arrived without your identity attached reads nothing rather than reading everything.
        </p>
        <p>
          Rendered PDFs and DOCX files are never stored. They are produced from your resume data at
          the moment you ask for one and discarded immediately after.
        </p>
      </Section>

      <Section n="05" title="How long we keep it">
        <p>
          Until you delete it. You can delete an individual application from the applications list,
          and you can replace your master profile at any time by uploading a new resume.
        </p>
        <p>
          Deleting your account deletes everything attached to it — profile, applications, resumes,
          cover letters and analyses — in the same operation. To request that, email us from the
          address you signed in with.
        </p>
      </Section>

      <Section n="06" title="Your rights">
        <p>
          You can ask for a copy of what we hold about you, ask us to correct it, or ask us to erase
          it. Depending on where you live you may also have the right to object to processing or to
          complain to a data protection regulator.
        </p>
      </Section>

      <Section n="07" title="Changes and contact">
        <p>
          If this policy changes in a way that affects you, we will say so here and update the date
          at the top. Questions about any of it, or a request under the section above, go to the
          contact address for the deployment you are using.
        </p>
        <p className="pt-1">
          See also the{" "}
          <Link href="/terms" className="font-semibold text-ink underline underline-offset-2">
            Terms of Service
          </Link>
          .
        </p>
      </Section>
    </>
  );
}
