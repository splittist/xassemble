import { AlertCircle, LoaderCircle } from "lucide-react";

export function Loading({ label = "Loading" }: { label?: string }) {
  return <div className="state-panel"><LoaderCircle className="spin" size={22} /><span>{label}…</span></div>;
}

export function ErrorMessage({ message }: { message: string }) {
  return <div className="error-banner" role="alert"><AlertCircle size={18} /><span>{message}</span></div>;
}
