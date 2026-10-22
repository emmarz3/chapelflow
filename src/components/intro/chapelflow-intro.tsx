import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useLocation } from "react-router-dom";
import {
  INTRO_CONFIG,
  INTRO_SEQUENCE,
  REDUCED_MOTION_SEQUENCE,
  shouldPlayIntro,
  type IntroStage,
} from "./intro.config";

const stageOrder: IntroStage[] = [
  "anticipation",
  "mark",
  "wordmark",
  "brandHold",
  "transitionToInstitution",
  "institution",
  "institutionHold",
  "transitionToApplication",
];

function storageHas(storage: Storage | undefined, key: string) {
  try {
    return storage?.getItem(key) === "1";
  } catch {
    return false;
  }
}

const GLOW_COLORS = ["#4c1798", "#6d2dce", "#2563eb", "#1685ee"] as const;
const GLOW_EASE = [0.22, 1, 0.36, 1] as const;

function PulsingGlow({ visible }: { visible: boolean }) {
  return (
    <motion.div
      className="cf-intro__glow"
      aria-hidden="true"
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{
        opacity: visible ? 1 : 0,
        scale: visible ? [0.94, 1.04, 0.96, 1] : 0.92,
      }}
      transition={{
        duration: 2.2,
        repeat: Infinity,
        ease: "easeInOut",
      }}
    >
      {GLOW_COLORS.map((color, index) => (
        <span
          key={color}
          className="cf-intro__glow-ring"
          style={{
            background: `radial-gradient(circle, ${color} 0%, transparent 70%)`,
            animationDelay: `${index * 0.18}s`,
          }}
        />
      ))}
    </motion.div>
  );
}

function FloatingParticles({ active }: { active: boolean }) {
  const particles = useMemo(
    () =>
      Array.from({ length: 18 }).map((_, index) => ({
        id: index,
        left: `${30 + (index % 6) * 10}%`,
        top: `${25 + Math.floor(index / 6) * 18}%`,
        delay: index * 0.06,
        duration: 1.6 + (index % 5) * 0.25,
        distance: 18 + (index % 4) * 12,
        opacity: 0.35 + (index % 3) * 0.18,
      })),
    [],
  );

  if (!active) return null;

  return (
    <div className="cf-intro__particles" aria-hidden="true">
      {particles.map((particle) => (
        <motion.span
          key={particle.id}
          className="cf-intro__particle"
          style={{
            left: particle.left,
            top: particle.top,
            opacity: particle.opacity,
          }}
          initial={{ y: 0, x: 0, opacity: 0 }}
          animate={{
            y: [-particle.distance, particle.distance * 0.35],
            x: [-particle.distance * 0.5, particle.distance * 0.5],
            opacity: [0, particle.opacity, 0],
          }}
          transition={{
            duration: particle.duration,
            delay: particle.delay,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}

function ChapelFlowMark({ active }: { active: boolean }) {
  const draw = { duration: 1.05, ease: GLOW_EASE } as const;
  return (
    <motion.svg
      className="cf-intro__mark"
      viewBox="0 0 240 220"
      initial={false}
      animate={{ opacity: active ? 1 : 0, scale: active ? 1 : 0.96 }}
      transition={{ duration: 0.32, ease: GLOW_EASE }}
    >
      <defs>
        <linearGradient id="cf-intro-gradient" x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#4c1798" />
          <stop offset="0.52" stopColor="#6d2dce" />
          <stop offset="1" stopColor="#1685ee" />
        </linearGradient>
        <filter id="cf-intro-glow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="6" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <motion.path
        d="M18 173 C53 143 83 147 119 170 C157 194 197 197 225 166 C209 211 165 220 119 194 C78 171 49 160 18 185 Z"
        fill="url(#cf-intro-gradient)"
        filter="url(#cf-intro-glow)"
        initial={{ clipPath: "inset(0 100% 0 0)" }}
        animate={{ clipPath: active ? "inset(0 0% 0 0)" : "inset(0 100% 0 0)" }}
        transition={draw}
      />
      <motion.path
        d="M52 151 V82 L120 31 L188 82 V118"
        fill="none"
        stroke="url(#cf-intro-gradient)"
        strokeWidth="16"
        strokeLinecap="square"
        strokeLinejoin="round"
        pathLength="1"
        filter="url(#cf-intro-glow)"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: active ? 1 : 0, opacity: active ? 1 : 0 }}
        transition={{ ...draw, delay: 0.18 }}
      />
      <motion.path
        d="M96 168 V114 C96 98 107 87 120 87 C133 87 144 98 144 114 V168"
        fill="url(#cf-intro-gradient)"
        filter="url(#cf-intro-glow)"
        initial={{ opacity: 0, scaleY: 0.4 }}
        animate={{ opacity: active ? 1 : 0, scaleY: active ? 1 : 0.4 }}
        style={{ transformOrigin: "120px 168px" }}
        transition={{ duration: 0.52, delay: 0.6, ease: GLOW_EASE }}
      />
      <motion.path
        d="M120 106 V147 M108 119 H132"
        fill="none"
        stroke="white"
        strokeWidth="7"
        strokeLinecap="square"
        initial={{ opacity: 0 }}
        animate={{ opacity: active ? 1 : 0 }}
        transition={{ duration: 0.28, delay: 0.82 }}
      />
      <motion.path
        d="M120 4 V31 M108 16 H132"
        fill="none"
        stroke="#4c1798"
        strokeWidth="7"
        strokeLinecap="square"
        initial={{ opacity: 0, scale: 0.85 }}
        animate={{ opacity: active ? 1 : 0, scale: active ? 1 : 0.85 }}
        style={{ transformOrigin: "120px 17px" }}
        transition={{ duration: 0.34, delay: 0.92, ease: GLOW_EASE }}
      />
      <motion.path
        d="M184 132 C208 112 229 119 234 121 C216 119 202 128 202 143 C202 158 216 166 234 162 C222 181 184 183 174 157 C169 146 174 138 184 132 Z"
        fill="url(#cf-intro-gradient)"
        filter="url(#cf-intro-glow)"
        initial={{ opacity: 0, x: 12 }}
        animate={{ opacity: active ? 1 : 0, x: active ? 0 : 12 }}
        transition={{ duration: 0.52, delay: 0.56, ease: GLOW_EASE }}
      />
    </motion.svg>
  );
}

function BrandSweep({ reverse = false }: { reverse?: boolean }) {
  const colors = ["#4c1798", "#6d2dce", "#2563eb", "#1685ee"];
  return (
    <div className={`cf-intro__sweep ${reverse ? "cf-intro__sweep--reverse" : ""}`} aria-hidden="true">
      {colors.map((color, index) => (
        <motion.span
          key={color}
          className="cf-intro__sweep-layer"
          style={{ background: color }}
          initial={{
            x: reverse ? "120%" : "-130%",
            y: reverse ? "18%" : "24%",
            rotate: reverse ? 8 : -8,
            filter: "blur(18px)",
            opacity: 0.55,
          }}
          animate={{
            x: reverse ? "-18%" : "16%",
            y: reverse ? "-16%" : "-20%",
            filter: "blur(6px)",
            opacity: 0.85,
          }}
          transition={{
            duration: 0.88,
            delay: index * 0.08,
            ease: GLOW_EASE,
          }}
        />
      ))}
    </div>
  );
}

export function ChapelFlowIntro() {
  const location = useLocation();
  const initialPathname = useRef(location.pathname);
  const reduceMotion = Boolean(useReducedMotion());
  const [stage, setStage] = useState<IntroStage>("anticipation");
  const [visible, setVisible] = useState(() => {
    if (typeof window === "undefined" || import.meta.env.MODE === "test") return false;
    return shouldPlayIntro(
      window.location.pathname,
      INTRO_CONFIG.mode,
      storageHas(window.sessionStorage, INTRO_CONFIG.storageKey),
      storageHas(window.localStorage, INTRO_CONFIG.storageKey),
    );
  });

  const finish = useCallback(() => {
    try {
      if (INTRO_CONFIG.mode === "session") {
        window.sessionStorage.setItem(INTRO_CONFIG.storageKey, "1");
      } else if (INTRO_CONFIG.mode === "once") {
        window.localStorage.setItem(INTRO_CONFIG.storageKey, "1");
      }
    } catch {
      // Storage can be unavailable in privacy-restricted browser contexts.
    }
    window.dispatchEvent(new CustomEvent("chapelflow:intro-complete"));
    setVisible(false);
  }, []);

  useLayoutEffect(() => {
    document.documentElement.classList.remove("cf-intro-pending");
  }, []);

  useEffect(() => {
    if (!visible) return;
    document.body.classList.add("cf-intro-active");
    const assets = [
      INTRO_CONFIG.brand.chapelFlowAsset,
      INTRO_CONFIG.brand.institutionAsset,
    ];
    for (const source of assets) {
      const image = new Image();
      image.src = source;
    }

    const sequence = reduceMotion ? REDUCED_MOTION_SEQUENCE : INTRO_SEQUENCE;
    let index = 0;
    let timer = 0;
    let cancelled = false;
    const advance = () => {
      if (cancelled) return;
      const step = sequence[index];
      if (!step) {
        finish();
        return;
      }
      setStage(step.stage);
      timer = window.setTimeout(() => {
        index += 1;
        advance();
      }, step.duration);
    };
    advance();

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      document.body.classList.remove("cf-intro-active");
    };
  }, [finish, reduceMotion, visible]);

  useEffect(() => {
    if (!visible || location.pathname === initialPathname.current) return;
    finish();
  }, [finish, location.pathname, visible]);

  const stageIndex = stageOrder.indexOf(stage);
  const markActive = stageIndex >= 1 && stageIndex <= 4;
  const showWordmark = stageIndex >= 2 && stageIndex <= 4;
  const showOfficial = stageIndex >= 3 && stageIndex <= 4;
  const showInstitution = stageIndex >= 5;
  const showGlow = stageIndex >= 1 && stageIndex <= 4;
  const showParticles = stageIndex >= 1 && stageIndex <= 4;
  const exiting = stage === "transitionToApplication";
  const overlayAnimation = useMemo(
    () =>
      exiting && !reduceMotion
        ? { clipPath: "inset(0 0 100% 0)" }
        : { clipPath: "inset(0 0 0% 0)" },
    [exiting, reduceMotion],
  );

  if (!visible) return null;

  return (
    <motion.div
      className={`cf-intro cf-intro--${stage}`}
      initial={{ opacity: 1, clipPath: "inset(0 0 0% 0)" }}
      animate={overlayAnimation}
      transition={
        exiting
          ? {
              duration: reduceMotion ? 0.24 : 0.82,
              delay: reduceMotion ? 0.04 : 0.18,
              ease: [0.76, 0, 0.24, 1],
            }
          : undefined
      }
      role="presentation"
    >
      <div className="cf-intro__visuals" aria-hidden="true">
        <AnimatePresence>
          {stage === "anticipation" && (
            <motion.span
              className="cf-intro__spark"
              initial={{ opacity: 0, scaleY: 0 }}
              animate={{ opacity: 1, scaleY: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.28, ease: GLOW_EASE }}
            />
          )}
        </AnimatePresence>

        {showGlow && <PulsingGlow visible={showGlow} />}
        {showParticles && <FloatingParticles active={showParticles} />}

        {stageIndex <= 4 && (
          <div className="cf-intro__brand-scene">
            <motion.div
              className="cf-intro__constructed-lockup"
              animate={{
                opacity: showOfficial ? 0 : 1,
                scale: showOfficial ? 0.985 : 1,
                y: showOfficial ? 6 : 0,
              }}
              transition={{ duration: 0.34, ease: GLOW_EASE }}
            >
              <ChapelFlowMark active={markActive} />
              <motion.div
                className="cf-intro__wordmark"
                initial={false}
                animate={{
                  opacity: showWordmark ? 1 : 0,
                  y: showWordmark ? 0 : 14,
                  letterSpacing: showWordmark ? "-0.055em" : "0.02em",
                  scale: showWordmark ? 1 : 0.98,
                }}
                transition={{ duration: 0.6, ease: GLOW_EASE }}
              >
                <span>Chapel</span>
                <strong>Flow</strong>
              </motion.div>
            </motion.div>
            <motion.img
              className="cf-intro__official-logo"
              src={INTRO_CONFIG.brand.chapelFlowAsset}
              alt=""
              initial={false}
              animate={{
                opacity: showOfficial ? 1 : 0,
                scale: showOfficial ? 1 : 0.985,
                y: showOfficial ? 0 : 8,
              }}
              transition={{ duration: 0.34, ease: GLOW_EASE }}
            />
          </div>
        )}

        {stage === "transitionToInstitution" && <BrandSweep />}

        {showInstitution && (
          <motion.div
            className="cf-intro__institution"
            initial={{ opacity: 0, scale: 0.94, y: 16, filter: "blur(8px)" }}
            animate={{ opacity: 1, scale: 1, y: 0, filter: "blur(0px)" }}
            transition={{ duration: 0.86, ease: GLOW_EASE }}
          >
            <div className="cf-intro__institution-stage">
              <motion.img
                src={INTRO_CONFIG.brand.institutionAsset}
                alt=""
                initial={{ y: 18, scale: 0.97 }}
                animate={{ y: 0, scale: 1 }}
                transition={{ duration: 0.82, ease: GLOW_EASE, delay: 0.08 }}
              />
              <motion.span
                className="cf-intro__institution-rule"
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ duration: 0.6, ease: GLOW_EASE, delay: 0.28 }}
              />
              <motion.p
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.52, ease: GLOW_EASE, delay: 0.38 }}
              >
                Chapel management platform
              </motion.p>
            </div>
            <motion.div
              className="cf-intro__institution-light"
              aria-hidden="true"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 1.4, ease: "easeInOut", delay: 0.12 }}
            />
          </motion.div>
        )}

        {exiting && <BrandSweep reverse />}
      </div>

      {!reduceMotion && stageIndex >= 1 && stageIndex < 7 && (
        <motion.button
          className="cf-intro__skip"
          type="button"
          onClick={finish}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.24, delay: 0.45 }}
        >
          Skip intro
        </motion.button>
      )}
    </motion.div>
  );
}
