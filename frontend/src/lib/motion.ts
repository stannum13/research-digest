export const notebookEase = [0.16, 1, 0.3, 1] as const;

export function staggerTransition(index: number, reducedMotion: boolean) {
  return {
    delay: reducedMotion ? 0 : index * 0.07,
    duration: reducedMotion ? 0 : 0.5,
    ease: notebookEase,
  };
}
