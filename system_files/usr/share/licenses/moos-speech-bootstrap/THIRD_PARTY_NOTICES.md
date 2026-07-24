# Arabic speech bootstrap — third-party notices

MoOS does not redistribute the Arabic diacritization model. When the user
explicitly sets up the local voice engine, `moos-prepare-speech-image` downloads
the model from Piper's pinned official `2023.11.14-2` release, verifies its
SHA-256 digest, and builds a rootless local container.

- Piper: <https://github.com/rhasspy/piper>, MIT license.
- piper-phonemize, copyright (c) 2023 Michael Hansen:
  <https://github.com/rhasspy/piper-phonemize>, MIT license.
- libtashkeel, copyright (c) Musharraf Omer:
  <https://github.com/mush42/libtashkeel>, MIT license.
- Speaches: <https://github.com/speaches-ai/speaches>, MIT license.

The MIT license permits use, copying, modification, distribution,
sublicensing, and sale provided its copyright and permission notice are
retained. The software and model are provided without warranty.
