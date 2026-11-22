# Retrieval comparison

24 answerable questions; a hit means a passage from an expected page is in the top k.

## Questions as a user would ask

| Method | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR |
| --- | --- | --- | --- | --- | --- |
| keyword | 0.50 | 0.62 | 0.75 | 0.92 | 0.61 |
| vector | 0.46 | 0.75 | 0.83 | 0.92 | 0.62 |
| hybrid | 0.50 | 0.75 | 0.79 | 0.83 | 0.64 |

## Same questions in the paper's terms

| Method | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR |
| --- | --- | --- | --- | --- | --- |
| keyword | 0.54 | 0.71 | 0.88 | 1.00 | 0.67 |
| vector | 0.54 | 0.71 | 0.83 | 0.88 | 0.64 |
| hybrid | 0.50 | 0.75 | 0.92 | 0.92 | 0.63 |
