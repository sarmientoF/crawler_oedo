# Crawler for edx CS courses

## Requirements

🚨 You need you `jupyter`, `notebook`(Can install them using pip), Also, you should have `ffmpeg` and `ffprobe` in your computer
. You can install ffmpeg using brew

```bash
brew install ffmpeg
```

## Instructions

1. It is better to create a virtual environment

```bash
python3 -m venv edx_env
```

2. Activate environment

```bash
source env/bin/activate
```

3. Install requirements

```bash
pip3 install -r requirements.txt
```

4. Create environment to use in jupyter

```bash
python3 -m ipykernel install --user --name edx_env --display-name "Python (edx crawler)"
```

5. Launch jupyter notebook

```bash
jupyter notebook .
```
