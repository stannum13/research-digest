import {
  InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  classifyPaper,
  clearSearchCache,
  createBackfillJob,
  createSynthesisRun,
  deleteSearchCacheEntry,
  getBackfillJobs,
  getClassificationStatus,
  getDigestRunDetail,
  getDigestStatus,
  getSearchCacheStatus,
  getLatestDigest,
  getPaperClassifications,
  getPapers,
  getStats,
  getSynthesisRun,
  getSynthesisRuns,
  runBackfillJob,
  runClassifications,
  runDigest,
  searchPapers,
  sendPaperFeedback,
  togglePaperSave,
} from "../lib/api";
import type {
  BackfillJob,
  BackfillJobRequest,
  BackfillJobsResponse,
  BackfillStatusName,
  ClassificationRun,
  ClassificationRunRequest,
  ClassificationStatus,
  DigestRunRequest,
  FeedbackSignal,
  PaperClassificationsResponse,
  PaperQueryParams,
  PapersResponse,
  PaperWithBreakdown,
  SearchCacheDeleteResponse,
  SearchCacheStatusResponse,
  SearchQueryParams,
  SearchResponse,
  SynthesisRun,
  SynthesisRunRequest,
} from "../types/api";

const PAGE_SIZE = 10;

export const digestKeys = {
  papers: (params: PaperQueryParams) => ["papers", params] as const,
  search: (params: SearchQueryParams) => ["search", params] as const,
  searchCacheStatus: ["search-cache-status"] as const,
  status: ["digest-status"] as const,
  latest: ["digest-latest"] as const,
  runDetails: ["digest-run-detail"] as const,
  runDetail: (runId: number | null | undefined) => ["digest-run-detail", runId] as const,
  backfillJobs: (status?: BackfillStatusName) => ["backfill-jobs", status ?? "all"] as const,
  backfillJob: (jobId: number | null | undefined) => ["backfill-job", jobId] as const,
  stats: ["stats"] as const,
  classificationStatus: ["classification-status"] as const,
  paperClassifications: (arxivId: string | null | undefined) =>
    ["paper-classifications", arxivId] as const,
  synthesisRuns: ["synthesis-runs"] as const,
  synthesisRun: (runId: number | null | undefined) => ["synthesis-run", runId] as const,
};

export function usePapers(params: PaperQueryParams) {
  return useInfiniteQuery<PapersResponse>({
    queryKey: digestKeys.papers(params),
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      getPapers({ ...params, page: Number(pageParam), page_size: PAGE_SIZE }),
    getNextPageParam: (lastPage) => {
      const loaded = lastPage.page * lastPage.page_size;
      return loaded < lastPage.total ? lastPage.page + 1 : undefined;
    },
  });
}

export function flattenPapers(data?: InfiniteData<PapersResponse>): PaperWithBreakdown[] {
  return data?.pages.flatMap((page) => page.items) ?? [];
}

export function useSearch(params: SearchQueryParams, enabled = true) {
  const hasSearchInput = Boolean(params.q || params.label_type || params.label);

  return useQuery<SearchResponse>({
    queryKey: digestKeys.search(params),
    queryFn: () => searchPapers(params),
    enabled: enabled && hasSearchInput,
  });
}

export function useSearchCacheStatus() {
  return useQuery<SearchCacheStatusResponse>({
    queryKey: digestKeys.searchCacheStatus,
    queryFn: getSearchCacheStatus,
  });
}

export function useClearSearchCache() {
  const queryClient = useQueryClient();

  return useMutation<SearchCacheDeleteResponse, Error, void>({
    mutationFn: clearSearchCache,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: digestKeys.searchCacheStatus });
      void queryClient.invalidateQueries({ queryKey: ["search"] });
    },
  });
}

export function useDeleteSearchCacheEntry() {
  const queryClient = useQueryClient();

  return useMutation<SearchCacheDeleteResponse, Error, number>({
    mutationFn: deleteSearchCacheEntry,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: digestKeys.searchCacheStatus });
      void queryClient.invalidateQueries({ queryKey: ["search"] });
    },
  });
}

export function useDigestStatus() {
  return useQuery({
    queryKey: digestKeys.status,
    queryFn: getDigestStatus,
    refetchInterval: 5000,
  });
}

export function useLatestDigest() {
  return useQuery({
    queryKey: digestKeys.latest,
    queryFn: getLatestDigest,
  });
}

export function useDigestRunDetail(runId: number | null | undefined) {
  return useQuery({
    queryKey: digestKeys.runDetail(runId),
    queryFn: () => getDigestRunDetail(runId as number),
    enabled: Boolean(runId),
  });
}

export function useStats() {
  return useQuery({
    queryKey: digestKeys.stats,
    queryFn: getStats,
  });
}

export function useClassificationStatus() {
  return useQuery({
    queryKey: digestKeys.classificationStatus,
    queryFn: getClassificationStatus,
  });
}

export function useBackfillJobs(status?: BackfillStatusName) {
  return useQuery({
    queryKey: digestKeys.backfillJobs(status),
    queryFn: () => getBackfillJobs(status ? { status } : {}),
  });
}

export function useRunDigest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload?: DigestRunRequest) => runDigest(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: digestKeys.status });
      void queryClient.invalidateQueries({ queryKey: digestKeys.latest });
      void queryClient.invalidateQueries({ queryKey: digestKeys.stats });
      void queryClient.invalidateQueries({ queryKey: ["papers"] });
    },
  });
}

export function useBackfillRange() {
  const queryClient = useQueryClient();

  return useMutation<BackfillJob, Error, BackfillJobRequest>({
    mutationFn: async (request) => {
      const categoryScope = request.category_scope?.filter(Boolean);
      return createBackfillJob({
        ...request,
        category_scope: categoryScope?.length ? categoryScope : undefined,
      });
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: digestKeys.status });
      void queryClient.invalidateQueries({ queryKey: digestKeys.latest });
      void queryClient.invalidateQueries({ queryKey: digestKeys.stats });
      void queryClient.invalidateQueries({ queryKey: digestKeys.runDetails });
      void queryClient.invalidateQueries({ queryKey: ["backfill-jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["papers"] });
    },
  });
}

export function useRunBackfillJob() {
  const queryClient = useQueryClient();

  return useMutation<BackfillJob, Error, number>({
    mutationFn: runBackfillJob,
    onSuccess: (job) => {
      queryClient.setQueryData(digestKeys.backfillJob(job.id), job);
      queryClient.setQueriesData<BackfillJobsResponse>({ queryKey: ["backfill-jobs"] }, (data) => {
        if (!data) {
          return data;
        }

        return {
          ...data,
          items: data.items.map((item) => (item.id === job.id ? job : item)),
        };
      });

      void queryClient.invalidateQueries({ queryKey: ["backfill-jobs"] });
      void queryClient.invalidateQueries({ queryKey: digestKeys.status });
      void queryClient.invalidateQueries({ queryKey: digestKeys.latest });
      void queryClient.invalidateQueries({ queryKey: digestKeys.stats });
      void queryClient.invalidateQueries({ queryKey: digestKeys.runDetails });
      void queryClient.invalidateQueries({ queryKey: ["papers"] });
    },
  });
}

export function useToggleSave() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: togglePaperSave,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["papers"] });
      void queryClient.invalidateQueries({ queryKey: digestKeys.stats });
    },
  });
}

export function usePaperClassifications(arxivId: string, enabled = true) {
  return useQuery({
    queryKey: digestKeys.paperClassifications(arxivId),
    queryFn: () => getPaperClassifications(arxivId),
    enabled: Boolean(arxivId) && enabled,
  });
}

export function useClassifyPaper(arxivId: string) {
  const queryClient = useQueryClient();

  return useMutation<PaperClassificationsResponse, Error, void>({
    mutationFn: () => classifyPaper(arxivId),
    onSuccess: (response) => {
      queryClient.setQueryData(digestKeys.paperClassifications(arxivId), response);
      void queryClient.invalidateQueries({ queryKey: digestKeys.classificationStatus });
    },
  });
}

export function useRunClassifications() {
  const queryClient = useQueryClient();

  return useMutation<ClassificationRun, Error, ClassificationRunRequest>({
    mutationFn: runClassifications,
    onSuccess: (response) => {
      queryClient.setQueryData<ClassificationStatus>(digestKeys.classificationStatus, response.status);
      void queryClient.invalidateQueries({ queryKey: ["papers"] });
      void queryClient.invalidateQueries({ queryKey: ["search"] });
      void queryClient.invalidateQueries({ queryKey: digestKeys.stats });
      void queryClient.invalidateQueries({ queryKey: digestKeys.classificationStatus });
    },
  });
}

export function useFeedbackMutation(arxivId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ signal, note }: { signal: FeedbackSignal; note?: string }) =>
      sendPaperFeedback(arxivId, signal, note),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: digestKeys.stats });
    },
  });
}

export function useSynthesisRuns() {
  return useQuery({
    queryKey: digestKeys.synthesisRuns,
    queryFn: getSynthesisRuns,
  });
}

export function useSynthesisRun(runId: number | null | undefined) {
  return useQuery({
    queryKey: digestKeys.synthesisRun(runId),
    queryFn: () => getSynthesisRun(runId as number),
    enabled: Boolean(runId),
  });
}

export function useCreateSynthesisRun() {
  const queryClient = useQueryClient();

  return useMutation<SynthesisRun, Error, SynthesisRunRequest>({
    mutationFn: createSynthesisRun,
    onSuccess: (run) => {
      void queryClient.invalidateQueries({ queryKey: digestKeys.synthesisRuns });
      void queryClient.invalidateQueries({ queryKey: digestKeys.synthesisRun(run.id) });
    },
  });
}
