# Reassembly_Crawler

A simple crawler for all agents of wormholes of Anisoptera's Reassembly [https://www.anisopteragames.com/](https://www.anisopteragames.com/), a great case to learn python crawlers.

System: Windows

## Usage

I recommend using conda env to use the script:

```
conda create -n python38
```

And run `init.bat` to download the dependencies.

After that, run `check_update.bat` to get the up-to-date links. By default, these are stored at `Inputs` directory.

Then run `download_all_grouped.bat` to download the agents from retrieved links, grouped by P-points. (You may want to run this script several times)

Run `random_agents.bat` to randomly choose agents from database, tweak `--download-num` to control the number of agents you want to get.

Then import these agents into Reassembly and have fun!
