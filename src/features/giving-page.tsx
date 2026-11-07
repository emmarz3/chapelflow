import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, CircleDollarSign, ExternalLink, LockKeyhole, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Badge, Button, PageHeader, useToast } from "../components/ui";
import { givingService, type PersonalGivingType } from "../services/chapelflow";

const givingOptions: { value: PersonalGivingType; title: string; description: string }[] = [
  { value: "OFFERING", title: "Offering", description: "A personal gift in support of chapel ministry." },
  { value: "TITHE", title: "Tithe", description: "A personal tithe given through the chapel." },
];

function messageFor(error: unknown) {
  return error instanceof Error ? error.message : "We could not complete that request. Please try again.";
}

export function GivingPage() {
  const toast = useToast();
  const [searchParams] = useSearchParams();
  const [givingType, setGivingType] = useState<PersonalGivingType>("OFFERING");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [formNotice, setFormNotice] = useState("");
  const returnReference = searchParams.get("reference");
  const verifiedReference = useRef<string | null>(null);

  const checkout = useMutation({
    mutationFn: givingService.beginPaystackCheckout,
    onSuccess: ({ data }) => window.location.assign(data.authorizationUrl),
    onError: (error) => toast(messageFor(error), "error"),
  });
  const verification = useMutation({
    mutationFn: givingService.verifyPaystackCheckout,
    onError: (error) => toast(messageFor(error), "error"),
  });

  useEffect(() => {
    if (returnReference && verifiedReference.current !== returnReference) {
      verifiedReference.current = returnReference;
      verification.mutate(returnReference);
    }
  }, [returnReference, verification]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!amount || Number(amount) <= 0) {
      setFormNotice("Enter an amount greater than ₦0.00.");
      return;
    }
    if (!confirmed) {
      setFormNotice("Please read and confirm the secure checkout notice before continuing.");
      return;
    }
    setFormNotice("");
    checkout.mutate({ givingType, amount, note: note.trim(), termsAccepted: confirmed });
  }

  const result = verification.data?.data;
  return (
    <div className="giving-checkout">
      <PageHeader
        eyebrow="Personal giving"
        title="Offerings and tithes"
        description="Give from your ChapelFlow account. Your payment is completed through Paystack's secure checkout."
      />

      {returnReference && (
        <section className="giving-result" aria-live="polite">
          {verification.isPending && <><CircleDollarSign className="spin" /><div><p className="eyebrow">Checking payment</p><h2>We are verifying your Paystack payment.</h2><p>Please do not make another payment while this check is in progress.</p></div></>}
          {result?.status === "SUCCESSFUL" && <><CheckCircle2 /><div><p className="eyebrow">Payment verified</p><h2>Thank you for your giving.</h2><p>₦{Number(result.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })} has been verified and recorded securely.</p></div><Badge tone="success">Recorded</Badge></>}
          {result?.status === "PENDING" && <><AlertTriangle /><div><p className="eyebrow">Payment pending</p><h2>Paystack has not confirmed this payment yet.</h2><p>Do not retry immediately. You can return later using the same account; the chapel office can also help with a verified reference.</p></div><Badge tone="warning">Pending</Badge></>}
          {result && result.status !== "SUCCESSFUL" && result.status !== "PENDING" && <><AlertTriangle /><div><p className="eyebrow">Payment not completed</p><h2>No giving has been recorded.</h2><p>Paystack did not confirm this checkout. If money left your account, contact the chapel office with your Paystack reference.</p></div><Badge tone="danger">Not recorded</Badge></>}
        </section>
      )}

      <div className="giving-checkout__grid">
        <section className="giving-checkout__form panel">
          <div className="giving-checkout__heading"><div><p className="eyebrow">1 · Choose your giving</p><h2>Make it clear before you pay.</h2></div><span><ShieldCheck /> Secure checkout</span></div>
          <form onSubmit={submit} noValidate>
            <fieldset className="giving-type-picker"><legend>Giving type</legend><div>{givingOptions.map((option) => <label key={option.value} className={givingType === option.value ? "is-selected" : ""}><input type="radio" name="givingType" value={option.value} checked={givingType === option.value} onChange={() => setGivingType(option.value)} /><span><strong>{option.title}</strong><small>{option.description}</small></span></label>)}</div></fieldset>
            <label className="field giving-amount"><span>Amount <em>Required</em></span><div><span aria-hidden="true">₦</span><input value={amount} onChange={(event) => setAmount(event.target.value)} inputMode="decimal" type="number" min="1" step="0.01" placeholder="0.00" required /></div><small>Payments are processed in Nigerian Naira (NGN).</small></label>
            <label className="field"><span>Private note <small>(optional)</small></span><textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} rows={3} placeholder="For example: September tithe" /></label>
            <label className="giving-confirmation"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><span>I have reviewed the amount and giving type. I understand that ChapelFlow will take me to Paystack to complete this payment securely.</span></label>
            {formNotice && <p className="form-note field__error" role="alert">{formNotice}</p>}
            <Button type="submit" loading={checkout.isPending} className="giving-submit" icon={<LockKeyhole />}>Continue to secure Paystack checkout <ExternalLink /></Button>
          </form>
        </section>

        <aside className="giving-checkout__notice" aria-label="Before you continue">
          <p className="eyebrow">Before you continue</p><h2>A careful, secure hand-off.</h2>
          <ol><li><span>01</span><p><strong>You pay with Paystack.</strong> ChapelFlow never asks for your card PIN, OTP, or bank password.</p></li><li><span>02</span><p><strong>Check the amount first.</strong> Confirm the giving type and amount before opening Paystack. A gateway transaction cannot be edited in ChapelFlow.</p></li><li><span>03</span><p><strong>A return screen is not proof of payment.</strong> ChapelFlow verifies the reference with Paystack and records only a successful payment.</p></li></ol>
          <div><ShieldCheck /><p>For a payment concern, keep your Paystack reference and <Link to="/contact">contact the chapel office</Link>.</p></div>
        </aside>
      </div>
    </div>
  );
}
