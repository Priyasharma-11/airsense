"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";
import { Button } from "./primitives";

export function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel = "Confirm", tone = "danger", onConfirm, loading, children }: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title: string;
  description: ReactNode;
  confirmLabel?: string;
  tone?: "danger" | "primary";
  onConfirm: () => void;
  loading?: boolean;
  children?: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild forceMount>
              <motion.div className="fixed inset-0 z-50 bg-slate-950/40 backdrop-blur-[2px]"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
            </Dialog.Overlay>
            <Dialog.Content asChild forceMount>
              <motion.div className="fixed left-1/2 top-1/2 z-50 w-[calc(100vw-32px)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-[20px] border border-line bg-elevated p-6 shadow-pop"
                initial={{ opacity: 0, scale: 0.96, y: "-46%", x: "-50%" }} animate={{ opacity: 1, scale: 1, y: "-50%", x: "-50%" }}
                exit={{ opacity: 0, scale: 0.97, y: "-48%", x: "-50%" }} transition={{ duration: 0.16 }}>
                <Dialog.Title className="font-display text-lg font-semibold text-fg">{title}</Dialog.Title>
                <Dialog.Description className="mt-2 text-sm leading-relaxed text-muted">{description}</Dialog.Description>
                {children}
                <div className="mt-6 flex justify-end gap-2">
                  <Dialog.Close asChild><Button variant="secondary">Cancel</Button></Dialog.Close>
                  <Button variant={tone} loading={loading} onClick={onConfirm}>{confirmLabel}</Button>
                </div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
