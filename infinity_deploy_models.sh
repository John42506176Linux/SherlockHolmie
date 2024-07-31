port=7997
small_embedding_model=nomic-ai/nomic-embed-text-v1.5
mixed_bread_model=mixedbread-ai/mxbai-rerank-large-v1
small_rerank_model=cross-encoder/ms-marco-TinyBERT-L-2-v2
volume=$PWD/data

sudo docker run -it --gpus all \
 -v $volume:/app/.cache \
 -p $port:$port \
 michaelf34/infinity:latest \
 v2 \
 --batch-size 32 \
 --model-id $mixed_bread_model \
 --model-id $small_embedding_model \
 --model-id $small_rerank_model \

 --port $port

port=7997
small_embedding_model=nomic-ai/nomic-embed-text-v1.5
rerank_model=cross-encoder/ms-marco-MiniLM-L-12-v2
mixed_bread_model=BAAI/bge-reranker-v2-m3
volume=$PWD/data
 infinity_emb v2
 --batch-size 32 \
 --model-id BAAI/bge-reranker-v2-m3 \
 --port $port

 infinity_emb v2 --model-id BAAI/bge-reranker-v2-m3

ssh -i "Embedder+Reranker.pem" ubuntu@ec2-54-244-190-49.us-west-2.compute.amazonaws.com

model=hkunlp/instructor-large
volume=$PWD/data # share a volume with the Docker container to avoid downloading weights every run

docker run --gpus all -p 8080:80 -v $volume:/data --pull always ghcr.io/huggingface/text-embeddings-inference:turing-1.5 --model-id $model