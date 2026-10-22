import { useEffect, useMemo, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import "./password-strength.css";

const CELL = { type: "spring", stiffness: 520, damping: 34, mass: 0.45 } as const;
const CROSSFADE = { type: "spring", stiffness: 260, damping: 34, mass: 0.8 } as const;
const INSTANT = { duration: 0 } as const;

const COMMON = /^(?:password|passw0rd|qwerty|letmein|welcome|admin|iloveyou|monkey|dragon|abc123|111111|123123|123456)/i;
const RUN = /(.)\1{3,}/;
const RUN_UP = /(?:0123|1234|2345|3456|4567|5678|6789|abcd|bcde|cdef|defg|qwer|wert|erty|asdf)/i;
const SYMBOL = /[!-/:-@[-`{-~]/;

export type PasswordRule = {
  id: string;
  label: string;
  test: (value: string) => boolean;
};

export type EvaluatedRule = PasswordRule & { met: boolean };

export type UsePasswordStrengthOptions = {
  rules?: readonly PasswordRule[];
  labels?: readonly string[];
  announceDelay?: number;
};

export type PasswordStrengthState = {
  score: number;
  max: number;
  label: string;
  rules: EvaluatedRule[];
  guessable: boolean;
  announcement: string;
};

export const defaultPasswordRules: readonly PasswordRule[] = [
  { id: "length", label: "12 characters or more", test: (v) => v.length >= 12 },
  { id: "case", label: "Upper and lower case", test: (v) => /[a-z]/.test(v) && /[A-Z]/.test(v) },
  { id: "digit", label: "A number", test: (v) => /\d/.test(v) },
  { id: "symbol", label: "A symbol", test: (v) => SYMBOL.test(v) },
];

export const passwordRulesForMinimumLength = (minimum: number): readonly PasswordRule[] => [
  { id: "length", label: `${minimum} characters or more`, test: (value) => value.length >= minimum },
  ...defaultPasswordRules.slice(1),
];

export const eightCharacterPasswordRules = passwordRulesForMinimumLength(8);
export const tenCharacterPasswordRules = passwordRulesForMinimumLength(10);

const defaultLabels = ["Empty", "Weak", "Fair", "Good", "Strong"] as const;

export function usePasswordStrength(
  value: string,
  { rules = defaultPasswordRules, labels = defaultLabels, announceDelay = 700 }: UsePasswordStrengthOptions = {},
): PasswordStrengthState {
  const state = useMemo(() => {
    const evaluated = rules.map((rule) => ({ ...rule, met: rule.test(value) }));
    const passed = evaluated.reduce((n, rule) => n + (rule.met ? 1 : 0), 0);
    const guessable = value.length > 0 && (COMMON.test(value) || RUN.test(value) || RUN_UP.test(value));
    const score = value.length === 0 ? 0 : guessable ? 1 : Math.min(rules.length, Math.max(1, passed));
    const label = labels[Math.min(score, labels.length - 1)] ?? "";
    const unmet = evaluated.filter((rule) => !rule.met);
    const announcement = value.length === 0 ? "" : [
      `Password strength ${label.toLowerCase()}.`,
      guessable ? "This is a commonly guessed pattern." : "",
      unmet.length === 0 ? "All requirements met." : `Still needed: ${unmet.map((rule) => rule.label.toLowerCase()).join(", ")}.`,
    ].filter(Boolean).join(" ");
    return { score, max: rules.length, label, rules: evaluated, guessable, announcement };
  }, [value, rules, labels]);

  const [settled, setSettled] = useState("");
  useEffect(() => {
    if (!state.announcement) {
      setSettled("");
      return;
    }
    const id = setTimeout(() => setSettled(state.announcement), announceDelay);
    return () => clearTimeout(id);
  }, [state.announcement, announceDelay]);

  return { ...state, announcement: settled };
}

export type PasswordStrengthProps = {
  value: string;
  rules?: readonly PasswordRule[];
  labels?: readonly string[];
  announceDelay?: number;
  showRules?: boolean;
  className?: string;
};

function toneFor(score: number, max: number) {
  if (score === 0 || max === 0) return "none";
  const ratio = score / max;
  if (ratio <= 0.34) return "danger";
  if (ratio <= 0.67) return "caution";
  return "safe";
}

export function PasswordStrength({
  value,
  rules = defaultPasswordRules,
  labels = defaultLabels,
  announceDelay = 700,
  showRules = true,
  className = "",
}: PasswordStrengthProps) {
  const { score, max, label, rules: evaluated, guessable, announcement } = usePasswordStrength(value, { rules, labels, announceDelay });
  const reduced = useReducedMotion();
  const tone = toneFor(score, max);
  const activeLabel = Math.min(score, labels.length - 1);

  return (
    <div className={`password-strength ${className}`}>
      <div role="meter" aria-label="Password strength" aria-valuemin={0} aria-valuemax={max} aria-valuenow={score} aria-valuetext={label} className="password-strength__meter" style={{ gridTemplateColumns: `repeat(${max}, minmax(0, 1fr))` }}>
        {Array.from({ length: max }, (_, index) => (
          <div key={index} className="password-strength__cell">
            <motion.span className={`password-strength__fill password-strength__fill--${tone}`} initial={false} animate={{ scaleX: index < score ? 1 : 0 }} transition={reduced ? INSTANT : { ...CELL, delay: index < score ? index * 0.03 : 0 }} />
          </div>
        ))}
      </div>
      <div className="password-strength__summary">
        <span className={`password-strength__label password-strength__label--${tone}`}>
          {labels.map((text, index) => (
            <motion.span key={`${index}-${text}`} aria-hidden="true" className="password-strength__label-item" initial={false} animate={{ opacity: index === activeLabel ? 1 : 0 }} transition={reduced ? INSTANT : CROSSFADE}>{text}</motion.span>
          ))}
        </span>
        <motion.span aria-hidden="true" className="password-strength__guessable" initial={false} animate={{ opacity: guessable ? 1 : 0 }} transition={reduced ? INSTANT : CROSSFADE}>Commonly guessed</motion.span>
      </div>
      {showRules && (
        <ul className="password-strength__rules">
          {evaluated.map((rule) => (
            <li key={rule.id} className="password-strength__rule">
              <span className={`password-strength__check ${rule.met ? "is-met" : ""}`} aria-hidden="true">
                <motion.svg viewBox="0 0 12 12" fill="none" aria-hidden="true" initial={false} animate={{ opacity: rule.met ? 1 : 0, scale: rule.met ? 1 : 0.6 }} transition={reduced ? INSTANT : CELL}><path d="M2 6.2 4.7 8.9 10 3.3" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" /></motion.svg>
              </span>
              <span className={rule.met ? "is-met" : ""}>{rule.label}</span>
              <span className="sr-only">{rule.met ? "met" : "not met"}</span>
            </li>
          ))}
        </ul>
      )}
      <p aria-live="polite" className="sr-only">{announcement}</p>
    </div>
  );
}

export default PasswordStrength;
