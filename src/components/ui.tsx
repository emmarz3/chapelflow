import {
  AlertCircle,
  Check,
  ChevronRight,
  LoaderCircle,
  Search,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import {
  createContext,
  useContext,
  useEffect,
  useId,
  useMemo,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";

export function Brand({
  compact = false,
  inverse = false,
}: {
  compact?: boolean;
  inverse?: boolean;
}) {
  return (
    <span className={`brand ${inverse ? "brand--inverse" : ""}`}>
      <img src="/chapelflow-mark.svg" alt="" />
      <span>
        <strong>ChapelFlow</strong>
        {!compact && <small>Chrisland University Chapel</small>}
      </span>
    </span>
  );
}

export function Button({
  variant = "primary",
  loading,
  icon,
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  loading?: boolean;
  icon?: ReactNode;
}) {
  return (
    <button
      className={`button button--${variant} ${className}`}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <LoaderCircle className="spin" aria-hidden="true" /> : icon}
      {children}
    </button>
  );
}

export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "success" | "warning" | "danger" | "purple";
  children: ReactNode;
}) {
  return (
    <span className={`badge badge--${tone}`}>
      {tone === "success" && <Check size={12} />} {children}
    </span>
  );
}

export function Field({
  label,
  hint,
  error,
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  error?: string;
}) {
  const id = useId();
  return (
    <label className={`field ${className}`} htmlFor={id}>
      <span>
        {label}
        {props.required && <em>Required</em>}
      </span>
      <input
        id={id}
        aria-describedby={hint || error ? `${id}-help` : undefined}
        aria-invalid={Boolean(error)}
        {...props}
      />
      {(error || hint) && (
        <small id={`${id}-help`} className={error ? "field__error" : ""}>
          {error || hint}
        </small>
      )}
    </label>
  );
}

export function SearchField({
  value,
  onChange,
  placeholder = "Search",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="search-field">
      <Search aria-hidden="true" size={18} />
      <span className="sr-only">{placeholder}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </header>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      {icon || <AlertCircle aria-hidden="true" />}
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function Skeleton({
  height = 20,
  width = "100%",
}: {
  height?: number;
  width?: string;
}) {
  return (
    <span className="skeleton" style={{ height, width }} aria-hidden="true" />
  );
}

export function LoadingState({
  label = "Loading content",
}: {
  label?: string;
}) {
  return (
    <div className="loading-state" role="status" aria-label={label}>
      <Skeleton height={18} width="34%" />
      <Skeleton height={92} />
      <div>
        <Skeleton height={120} />
        <Skeleton height={120} />
        <Skeleton height={120} />
      </div>
    </div>
  );
}

export function ErrorState({
  title = "This content could not be loaded",
  description = "Check your connection and try again.",
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="error-state" role="alert">
      <AlertCircle />
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function Modal({
  open,
  title,
  description,
  onClose,
  children,
  footer,
}: {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) =>
      event.key === "Escape" && onClose();
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="modal-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onMouseDown={onClose}
        >
          <motion.section
            role="dialog"
            aria-modal="true"
            aria-labelledby="dialog-title"
            className="modal"
            initial={{ opacity: 0, y: 18, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.98 }}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <button
              className="icon-button modal__close"
              onClick={onClose}
              aria-label="Close dialog"
            >
              <X />
            </button>
            <div className="modal__header">
              <h2 id="dialog-title">{title}</h2>
              {description && <p>{description}</p>}
            </div>
            <div className="modal__body">{children}</div>
            {footer && <footer className="modal__footer">{footer}</footer>}
          </motion.section>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

interface ToastItem {
  id: number;
  message: string;
  tone: "success" | "error";
}
const ToastContext = createContext<
  (message: string, tone?: ToastItem["tone"]) => void
>(() => undefined);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const show = useMemo(
    () =>
      (message: string, tone: ToastItem["tone"] = "success") => {
        const id = Date.now();
        setToasts((items) => [...items, { id, message, tone }]);
        window.setTimeout(
          () => setToasts((items) => items.filter((item) => item.id !== id)),
          4000,
        );
      },
    [],
  );
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="toast-region" aria-live="polite">
        <AnimatePresence>
          {toasts.map((toast) => (
            <motion.div
              key={toast.id}
              className={`toast toast--${toast.tone}`}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
            >
              {toast.tone === "success" ? <Check /> : <AlertCircle />}
              <span>{toast.message}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}
export const useToast = () => useContext(ToastContext);

export function SectionLink({ children }: { children: ReactNode }) {
  return (
    <span className="section-link">
      {children}
      <ChevronRight size={16} />
    </span>
  );
}
