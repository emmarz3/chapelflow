import { useId, useState } from "react";
import { PasswordStrength } from "./password-strength";
import "./password-strength-demo.css";

export function PasswordStrengthDemo() {
  const id = useId();
  const [value, setValue] = useState("");
  return (
    <div className="password-strength-demo">
      <label htmlFor={id}>New password</label>
      <input id={id} type="password" value={value} autoComplete="new-password" spellCheck={false} onChange={(event) => setValue(event.target.value)} placeholder="Type a password" />
      <PasswordStrength value={value} className="password-strength-demo__meter" />
    </div>
  );
}

export default PasswordStrengthDemo;
