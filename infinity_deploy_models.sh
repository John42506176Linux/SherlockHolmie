port=7997
mixed_bread_model=mixedbread-ai/mxbai-rerank-large-v1
mixed_bread_embedding_model=mixedbread-ai/mxbai-embed-large-v1
jina_model=jinaai/jina-reranker-v2-base-multilingual
mixed_bread_small=mixedbread-ai/mxbai-rerank-xsmall-v1
gte_rerank_model=Alibaba-NLP/gte-multilingual-reranker-base
volume=$PWD/data

sudo docker run -it --gpus all \
 -v $volume:/app/.cache \
 -p $port:$port \
 michaelf34/infinity:latest \
 v2 \
 --batch-size 2 \
 --model-id $mixed_bread_embedding_model \
 --model-id $gte_rerank_model \
 --port $port


model=BAAI/bge-large-en-v1.5
volume=$PWD/data # share a volume with the Docker container to avoid downloading weights every run

docker run --gpus all -p 8080:80 -v $volume:/data --pull always 	ghcr.io/huggingface/text-embeddings-inference:turing-1.5 --model-id $model

port=7998
mixed_bread_model=corto-ai/mxbai-rerank-large-v1-onnx-quant
volume=$PWD/data

sudo docker run -it --gpus all \
 -v $volume:/app/.cache \
 -p $port:$port \
 michaelf34/infinity:latest \
 v2 \
 --batch-size 32 \
 --model-id $mixed_bread_model \
 --engine optimum \
 --port $port


port=7997
small_embedding_model=nomic-ai/nomic-embed-text-v1.5
in_ranker_model=unicamp-dl/InRanker-base
rerank_model=cross-encoder/ms-marco-MiniLM-L-12-v2
mixed_bread_model=BAAI/bge-reranker-v2-m3
volume=$PWD/data
 infinity_emb v2
 --batch-size 32 \
 --model-id BAAI/bge-reranker-v2-m3 \
 --port $port

 infinity_emb v2 --model-id BAAI/bge-reranker-v2-m3

ssh -i "Embedder+Reranker.pem" ubuntu@ec2-35-90-19-128.us-west-2.compute.amazonaws.com
ssh -L 8888:localhost:8888  -i "Embedder+Reranker.pem" ubuntu@ec2-35-90-19-128.us-west-2.compute.amazonaws.com
ssh -L 8890:localhost:8890 -i "Embedder+Reranker.pem" ubuntu@ec2-35-90-19-128.us-west-2.compute.amazonaws.com
model=hkunlp/instructor-large
volume=$PWD/data # share a volume with the Docker container to avoid downloading weights every run

docker run --gpus all -p 8080:80 -v $volume:/data --pull always ghcr.io/huggingface/text-embeddings-inference:turing-1.5 --model-id $model