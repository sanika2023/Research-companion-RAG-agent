export type PaperCredit = {
  title: string;
  authors: string;
  arxivId: string;
  licence: string;
  licenceUrl: string;
};

const CC_BY_4 = { licence: "CC BY 4.0", licenceUrl: "https://creativecommons.org/licenses/by/4.0/" };

// The papers loaded on the public demo. CC BY requires crediting them wherever they are served;
// keep this in sync with what's uploaded there (licences checked on arXiv, 2026-11-26).
export const DEMO_PAPERS: PaperCredit[] = [
  {
    title:
      "Consistency and Uncertainty: Identifying Unreliable Responses From Black-Box " +
      "Vision-Language Models for Selective Visual Question Answering",
    authors: "Zaid Khan, Yun Fu",
    arxivId: "2404.10193",
    ...CC_BY_4,
  },
  {
    title: "Enhancing Hallucination Detection through Noise Injection",
    authors:
      "Litian Liu, Reza Pourreza, Sunny Panchal, Apratim Bhattacharyya, Yubing Jian, Yao Qin, " +
      "Roland Memisevic",
    arxivId: "2502.03799",
    ...CC_BY_4,
  },
  {
    title: "SPUQ: Perturbation-Based Uncertainty Quantification for Large Language Models",
    authors: "Xiang Gao, Jiaxin Zhang, Lalla Mouatadid, Kamalika Das",
    arxivId: "2403.02509",
    ...CC_BY_4,
  },
];
