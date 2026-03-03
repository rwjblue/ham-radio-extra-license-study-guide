window.HAM_EXTRA_ARTIFACTS = {
  "default_style": "qa",
  "style_choices": [
    {
      "id": "qa",
      "title": "I want direct exam practice",
      "note": "Best for drilling exam-style prompts and answers. Recommended starting point.",
      "items": [
        {
          "href": "./amateur-extra-license-prep-qa.pdf",
          "label": "Q&A PDF",
          "description": "Printable exam-style workbook."
        },
        {
          "href": "./amateur-extra-license-prep-qa.epub",
          "label": "Q&A EPUB",
          "description": "E-reader exam-style workbook."
        },
        {
          "href": "./amateur-extra-license-prep-qa.mp3.placeholder.txt",
          "label": "Q&A Audio Book",
          "description": "Placeholder until Q&A chapter audio is rendered and merged."
        }
      ]
    },
    {
      "id": "facts",
      "title": "I want concise memorization",
      "note": "Best for quickly memorizing correct answers in statement form.",
      "items": [
        {
          "href": "./amateur-extra-license-prep-facts.pdf",
          "label": "Facts PDF",
          "description": "Printable statement-style workbook."
        },
        {
          "href": "./amateur-extra-license-prep-facts.epub",
          "label": "Facts EPUB",
          "description": "E-reader statement-style workbook."
        },
        {
          "href": "./amateur-extra-license-prep-fact.mp3.placeholder.txt",
          "label": "Facts Audio Book",
          "description": "Placeholder until rendered chapter audio is merged."
        }
      ]
    },
    {
      "id": "augmented",
      "title": "I want extra context (experimental)",
      "note": "Adds AI-generated prose context on top of canonical answers. Depending on the source pool and build inputs, this may sometimes look close to the non-augmented versions.",
      "items": [
        {
          "href": "./amateur-extra-license-prep-augmented-facts.pdf",
          "label": "Augmented Facts PDF",
          "description": "Facts plus extra explanation context."
        },
        {
          "href": "./amateur-extra-license-prep-augmented-qa.pdf",
          "label": "Augmented Q&A PDF",
          "description": "Q&A plus extra explanation context."
        },
        {
          "href": "./amateur-extra-license-prep-augmented-facts.epub",
          "label": "Augmented Facts EPUB",
          "description": "E-reader facts plus extra context."
        },
        {
          "href": "./amateur-extra-license-prep-augmented-qa.epub",
          "label": "Augmented Q&A EPUB",
          "description": "E-reader Q&A plus extra context."
        }
      ]
    }
  ],
  "sections": [
    {
      "title": "Static Facts",
      "items": [
        {
          "href": "./amateur-extra-license-prep-facts.pdf",
          "label": "facts.pdf",
          "description": "Printable static facts workbook."
        },
        {
          "href": "./amateur-extra-license-prep-facts-dark.pdf",
          "label": "facts-dark.pdf",
          "description": "Dark-theme static facts workbook."
        },
        {
          "href": "./amateur-extra-license-prep-facts.epub",
          "label": "facts.epub",
          "description": "E-reader version of static facts."
        },
        {
          "href": "./amateur-extra-license-prep-facts.txt",
          "label": "facts.txt",
          "description": "Plain-text static facts output."
        }
      ]
    },
    {
      "title": "Q&A Facts",
      "items": [
        {
          "href": "./amateur-extra-license-prep-qa.pdf",
          "label": "qa.pdf",
          "description": "Printable Q&A workbook."
        },
        {
          "href": "./amateur-extra-license-prep-qa-dark.pdf",
          "label": "qa-dark.pdf",
          "description": "Dark-theme Q&A workbook."
        },
        {
          "href": "./amateur-extra-license-prep-qa.epub",
          "label": "qa.epub",
          "description": "E-reader version of Q&A output."
        },
        {
          "href": "./amateur-extra-license-prep-qa.txt",
          "label": "qa.txt",
          "description": "Plain-text Q&A output."
        }
      ]
    },
    {
      "title": "Augmented (Optional)",
      "note": "Augmented artifacts include AI-generated prose in addition to the canonical answer.",
      "items": [
      {
        "href": "./amateur-extra-license-prep-augmented-facts.pdf",
        "label": "augmented/facts.pdf",
        "description": "Augmented static facts PDF."
      },
      {
        "href": "./amateur-extra-license-prep-augmented-qa.pdf",
        "label": "augmented/qa.pdf",
        "description": "Augmented Q&A PDF."
      },
      {
        "href": "./amateur-extra-license-prep-augmented-facts.epub",
        "label": "augmented/facts.epub",
        "description": "Augmented static facts EPUB."
      },
      {
        "href": "./amateur-extra-license-prep-augmented-qa.epub",
        "label": "augmented/qa.epub",
        "description": "Augmented Q&A EPUB."
      }
    ]
    },
    {
      "title": "Audio Artifacts",
      "items": [
        {
          "href": "./amateur-extra-license-prep-fact.mp3.placeholder.txt",
          "label": "audio/fact/book.mp3",
          "description": "Placeholder until rendered chapter audio is merged."
        },
        {
          "href": "./amateur-extra-license-prep-fact-script.txt",
          "label": "audio/fact/script.txt",
          "description": "Fact narration script."
        },
        {
          "href": "./amateur-extra-license-prep-fact-manifest.json",
          "label": "audio/fact/manifest.json",
          "description": "Fact chapter manifest for rendering/verification."
        },
        {
          "href": "./amateur-extra-license-prep-qa.mp3.placeholder.txt",
          "label": "audio/qa/book.mp3",
          "description": "Placeholder until Q&A chapter audio is rendered and merged."
        },
        {
          "href": "./amateur-extra-license-prep-qa-script.txt",
          "label": "audio/qa/script.txt",
          "description": "Q&A narration script."
        },
        {
          "href": "./amateur-extra-license-prep-qa-manifest.json",
          "label": "audio/qa/manifest.json",
          "description": "Q&A chapter manifest for rendering/verification."
        }
      ]
    },
    {
      "title": "Pool Data",
      "items": [
        {
          "href": "./pool/extra_pool.json",
          "download": "amateur-extra-license-prep-pool.json",
          "label": "pool/extra_pool.json",
          "description": "Canonical extracted pool JSON. Figure files are in pool/assets/."
        },
      {
        "href": "./pool/extra_pool_prose.json",
        "download": "amateur-extra-license-prep-pool-prose.json",
        "label": "pool/extra_pool_prose.json",
        "description": "Optional prose-augmented pool JSON (if generated)."
      },
        {
          "href": "https://github.com/rwjblue/ham-radio-extra-license-study-guide/releases/latest",
          "label": "Release Bundles",
          "description": "Download complete JSON + image bundles from the latest GitHub release."
        }
      ]
    }
  ]
}
;
