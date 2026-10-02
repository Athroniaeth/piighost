from piighost.config import load_pipeline, load_thread_pipeline

stateless = load_pipeline("pipeline.toml")  # no [memory]
thread = load_thread_pipeline("thread.toml")  # has [memory]
