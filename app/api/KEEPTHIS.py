from swarm import Agent, Swarm  # type: ignore

# Define the agents with specific roles
guideline_detector = Agent(
    name="Directive Language Agent for Brand Licensing",
    instructions="""Identify whether the text contains specific rules or instructions that mandate actions, using prescriptive language like 'must,' 'required,' 'may not,' or 'should.' Distinguish such texts from those that use general descriptions or intentions without specifying required actions. Focus on finding terms that indicate obligations or prohibitions.
    Determine if the text provides detailed instructions related to specific actions, procedures, or conditions. Compare this to broader descriptions that do not give precise actions but rather introduce, define, or describe a set of standards.
    Evaluate if the text includes specific conditions that apply directly to actions or processes, such as how advertising or branding should be conducted, or how specific terms should be adhered to. Distinguish these from descriptions of the scope, intent, or general purpose of the standards.
    IF YOU THINK THE TEXT IS A GUIDELINE, ONLY RETURN True, OTHERWISE ONLY RETURN False!!!
    """,
)

swarm = Swarm()

page_text = """
Medium Format Star Diameter Version Scaling Factor Width Ratio Width to Height Ratio Version, alignment

Star (database, logo size) Star Diameter Word Mark to Star

Ads 2/1 ad 33.6 mm M 33.6 % 50.4 mm 150 % 1:6 ML, left-aligned
1/1 ad 28 mm M 28 % 42 mm 150 % 1:6 ML, left-aligned
Dealer ads 135 x 200 mm 18 mm M 18 % 2 7 mm 150 % 1:6 S, left-aligned
180 x 240 mm 24 mm M 24 % 36 mm 150 % 1:6 ML, left-aligned
90 x 250 mm 18 mm M 18 % 27 mm 150 % 1:6 S, left-aligned
240 x 180 mm 24 mm M 24 % 36 mm 150 % 1:6 ML, left-aligned
180 x 135 mm 18 mm M 18 % 27 mm 150 % 1:6 S, left-aligned
180 x 90 mm 18 mm M 18 % 27 mm 150 % 1:6 S, left-aligned
45 x 250 mm 18 mm M 18 % 27 mm 150 % 1:6 S, left-aligned
Flyers DIN long 21 mm M 21 % 31.5 mm 150 % 1:6 ML, left-aligned
Posters Din A1, portrait 79.2 mm L 79.2 % 118.8 mm 150 % 1:6 ML, left-aligned
Din A1, landscape 84.1 mm L 84.1 % 126.15 mm 150 % 1:6 ML, left-aligned
Catalogue 285 x 193 mm 25.7 mm M 12.85 % 38.55 mm 150 % 1:6 MB-word-mark
Roll-ups 850 x 2100 mm 170 mm L 170 % 225 mm 150 % 1:6 ML, left-aligned
Presentation walls 4000 x 2000 mm 320 mm L 320 % 480 mm 150 % 1:6 ML, left-aligned
Online Banners 336 x 600 px Final definition pending
400 x 400 px Final definition pending
160 x 600 px Final definition pending
728 x 180 px Final definition pending
728 x 90 px Final definition pending
300 x 250 px Final definition pending
All formats Final definition pending
"""

# Prepare messages for the first agent
messages = [{"role": "user", "content": page_text}]

# Run the first agent for the current page's text
results = swarm.run(agent=guideline_detector, messages=messages)
guideline_result = results.messages[0]["content"]
print("Directive Language Agent for Brand Licensing result:", guideline_result)

# Use the output of the first agent as input for the second agent
messages = [{"role": "user", "content": page_text}, {"role": "assistant", "content": guideline_result}]
