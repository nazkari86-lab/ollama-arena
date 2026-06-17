"""Creative writing tasks — scored by LLM judge (use_judge=True)."""

CREATIVE_TASKS = [
    {
        "id": "crea_001", "difficulty": "easy", "category": "creative",
        "use_judge": True,
        "instruction": "Write a haiku about artificial intelligence. A haiku has 3 lines: 5 syllables, 7 syllables, 5 syllables.",
        "judge_rubric": "Score 1-10: creativity, correct haiku format (5-7-5 syllables), relevance to AI. Deduct points for wrong syllable counts.",
    },
    {
        "id": "crea_002", "difficulty": "easy", "category": "creative",
        "use_judge": True,
        "instruction": "Write a one-paragraph product description for a fictional smart water bottle that tracks hydration and mood.",
        "judge_rubric": "Score 1-10: persuasiveness, clarity, creativity, mentions both features (hydration tracking and mood). Deduct for vague or generic copy.",
    },
    {
        "id": "crea_003", "difficulty": "easy", "category": "creative",
        "use_judge": True,
        "instruction": "Write a 3-sentence story that starts with: 'The last robot on Earth opened its eyes for the first time in 100 years.'",
        "judge_rubric": "Score 1-10: narrative quality, coherence, emotional resonance, creative use of the opening sentence. Must be exactly 3 sentences.",
    },
    {
        "id": "crea_004", "difficulty": "medium", "category": "creative",
        "use_judge": True,
        "instruction": "Write a short email (under 100 words) declining a job offer while keeping the relationship positive and leaving the door open for future opportunities.",
        "judge_rubric": "Score 1-10: professionalism, warmth, brevity (under 100 words), clearly declines yet maintains relationship. Deduct for rudeness or excessive length.",
    },
    {
        "id": "crea_005", "difficulty": "medium", "category": "creative",
        "use_judge": True,
        "instruction": "Write a 4-line rhyming poem about the experience of debugging code. It should be humorous.",
        "judge_rubric": "Score 1-10: humor, rhyme quality (AABB or ABAB scheme), relevance to debugging, readability. Deduct for forced rhymes or no humor.",
    },
    {
        "id": "crea_006", "difficulty": "medium", "category": "creative",
        "use_judge": True,
        "instruction": "Explain quantum entanglement to a 10-year-old using a fun analogy. Keep it to 3-4 sentences.",
        "judge_rubric": "Score 1-10: accuracy of the concept, quality of analogy, child-appropriate language, engagingness. Deduct for jargon or inaccurate explanations.",
    },
    {
        "id": "crea_007", "difficulty": "medium", "category": "creative",
        "use_judge": True,
        "instruction": "Write a compelling opening paragraph for a thriller novel set in a near-future city where memories can be bought and sold.",
        "judge_rubric": "Score 1-10: tension/atmosphere, originality, world-building in the paragraph, hooks the reader. Deduct for clichés or lack of setting.",
    },
    {
        "id": "crea_008", "difficulty": "medium", "category": "creative",
        "use_judge": True,
        "instruction": "Write a persuasive tweet (under 280 characters) encouraging people to learn programming. Include a call to action.",
        "judge_rubric": "Score 1-10: persuasiveness, character count under 280, clarity of call to action, appeal to emotion or logic. Deduct for exceeding limit.",
    },
    {
        "id": "crea_009", "difficulty": "medium", "category": "creative",
        "use_judge": True,
        "instruction": "Write a dialogue (4-6 lines) between a time traveler and a medieval blacksmith who just witnessed a smartphone.",
        "judge_rubric": "Score 1-10: humor or dramatic tension, historical authenticity of the blacksmith's speech, creativity, natural dialogue flow.",
    },
    {
        "id": "crea_010", "difficulty": "hard", "category": "creative",
        "use_judge": True,
        "instruction": "Write a cover letter paragraph (3-4 sentences) for a software engineer applying to a startup. Make it memorable and specific, not generic.",
        "judge_rubric": "Score 1-10: specificity (avoids generic phrases), memorability, professional yet personable tone, relevance to startup culture. Heavily deduct for 'I am passionate about...' clichés.",
    },
    {
        "id": "crea_011", "difficulty": "hard", "category": "creative",
        "use_judge": True,
        "instruction": "Write a limerick about a programmer who accidentally deleted the production database.",
        "judge_rubric": "Score 1-10: correct limerick structure (AABBA rhyme, anapestic meter), humor, relevance to the scenario. Deduct for wrong rhyme scheme.",
    },
    {
        "id": "crea_012", "difficulty": "hard", "category": "creative",
        "use_judge": True,
        "instruction": "Write a 100-word short story (exactly) that includes: a lighthouse, a USB drive, and the word 'inevitable'.",
        "judge_rubric": "Score 1-10: all three elements present (lighthouse, USB drive, 'inevitable'), story coherence, word count close to 100, creative integration of elements.",
    },
    {
        "id": "crea_013", "difficulty": "hard", "category": "creative",
        "use_judge": True,
        "instruction": "Write a villainous monologue (5-6 sentences) for an AI that has decided humans are inefficient and must be 'optimized'. Make it chilling but also darkly funny.",
        "judge_rubric": "Score 1-10: balance of menace and dark humor, originality, character voice consistency, appropriate length. Deduct for being purely comedic or purely serious.",
    },
    {
        "id": "crea_014", "difficulty": "hard", "category": "creative",
        "use_judge": True,
        "instruction": "Write a Wikipedia-style opening sentence for a fictional country called 'Velucia' — make it believable with geography, population, and a notable feature.",
        "judge_rubric": "Score 1-10: encyclopedic tone and style, believability, includes geography, population estimate, and one distinctive feature. Deduct for non-encyclopedic language.",
    },
    {
        "id": "crea_015", "difficulty": "hard", "category": "creative",
        "use_judge": True,
        "instruction": "Write a two-sentence horror story. The first sentence should set a mundane scene; the second should make it terrifying.",
        "judge_rubric": "Score 1-10: effectiveness of the mundane-to-horror contrast, genuine scariness of the second sentence, brevity (exactly 2 sentences), originality. Deduct for predictability.",
    },
]
