import type { Metadata } from "next";
import Link from "next/link";
import { Bullets, Lede, Section, Title } from "../parts";

export const metadata: Metadata = {
  title: "Terms of Service · recast",
  description: "The terms you agree to by using Recast.",
};

// Baseline text. Like the privacy policy, this is a starting point written to
// match what the product actually does — not legal advice, and worth a review
// before the service is offered to the public.
const UPDATED = "12 September 2026";

export default function Terms() {
  return (
    <>
      <Title updated={UPDATED}>Terms of Service</Title>

      <Lede>
        These terms cover your use of Recast. By signing in you agree to them. If
        you do not, do not sign in.
      </Lede>

      <Section n="01" title="What Recast does">
        <p>
          Recast reads a resume you supply and a job description you paste, and produces a version
          of that resume reordered and reworded for the role, along with a score for how well the
          two match. It selects and rephrases material you already wrote. It is not a writing
          service and it does not invent experience on your behalf.
        </p>
      </Section>

      <Section n="02" title="Your account">
        <p>
          You sign in with a Google account. You are responsible for what happens under it, so keep
          access to it secure. One account is for one person — do not share it.
        </p>
        <p>
          You must be old enough to enter a contract where you live, and you must not be barred from
          using the service under applicable law.
        </p>
      </Section>

      <Section n="03" title="Your content">
        <p>
          Your resume and everything derived from it stay yours. You grant us only the permission
          needed to run the service: to store your documents, to process them, and to send the
          relevant text to the model provider that performs the rewriting.
        </p>
        <p>
          You confirm that you have the right to upload what you upload, and that what it says about
          you is true.
        </p>
      </Section>

      <Section n="04" title="What you agree not to do">
        <Bullets
          items={[
            "Upload someone else's resume or personal details without their permission.",
            "Use the output to misrepresent your qualifications, experience or identity.",
            "Attempt to break, overload, scrape or reverse-engineer the service.",
            "Use the service for anything unlawful.",
          ]}
        />
      </Section>

      <Section n="05" title="Review your output">
        <p>
          Recast is an aid, not an authority. It is built to be conservative — every line traces
          back to something you wrote, and an automated check verifies each rewrite against your own
          words — but automated systems get things wrong, and the match score is an estimate rather
          than a prediction.
        </p>
        <p>
          You are the one signing your name to the document. Read every tailored resume and cover
          letter before you send it. Anything you send is your responsibility.
        </p>
      </Section>

      <Section n="06" title="Availability">
        <p>
          The service is provided as-is and as-available. We do not promise it will be uninterrupted
          or error-free, and we may change or withdraw features. Where the law allows, we exclude
          liability for indirect or consequential loss — including any job you did or did not get.
        </p>
      </Section>

      <Section n="07" title="Ending it">
        <p>
          You can stop using Recast at any time, and you can ask us to delete your account and
          everything in it. We may suspend or close an account that breaches these terms.
        </p>
      </Section>

      <Section n="08" title="Changes">
        <p>
          We may update these terms. Material changes will be noted here with a new date at the top,
          and continuing to use the service after that means you accept them.
        </p>
        <p className="pt-1">
          See also the{" "}
          <Link href="/privacy" className="font-semibold text-ink underline underline-offset-2">
            Privacy Policy
          </Link>
          .
        </p>
      </Section>
    </>
  );
}
