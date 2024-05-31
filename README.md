
# Welcome to Sherlock

Important Folders 
- /cdk_stacks -  Important to deploy Code to AWS
    - CDK Stacks
    - Cluster Stack - Code for deploying subreddit downloader Fargate task to aws
    - VPC Stack - Code for deploying VPC
    - Lambda Stack - Code for deploying AWS Lambda Endpoint for public use.
    - Database Stack - Code for deploying Datatabase
-/Lambda - Code for AWS Lambda task to start subreddit downloader
-/Backend 
    - Co
## Useful commands

 * cdk deploy -  Deploy stack to aws.
 * tasks/deploy.sh - Deploy

## How to deploy report generation service locally
 * cd backend
 * docker-compose up --build report-task
 * Endpoints:

## POST `/process_space`

This endpoint processes a given space and returns the pain points and personas.

### Request Body

The request body should be a JSON object with the following properties:

- `space` (string, required): The space to process.

Additonal parameters:

- `fast` (bool,optional) : Controls whether the database uses the index or not - Default:True
- `threshold`(bool,optional): Controls how many posts are analyzed Default: 0.55

### Response

The response is a JSON object with the following properties:

- `Initialization Time` (number): The time taken to initialize the space.
- `Pain Points` (array): An array of pain points for the given space.
- `Personas` (array): An array of personas for the given space.

### Example

Request:

```json
{
    "space": "CryptoCurrency",
    "fast": false,
    "threshold":0.55
}

{
  "Initialization Time": 1862.1723973751068,
  "Pain Points": [
    {
      "Pain Point": "Lack of Popularity and Recognition",
      "Description": "Despite its creative premise and well-written story, Undead Unluck struggles to gain the widespread recognition and popularity it deserves, leaving fans concerned about its future and potential.",
      "Quote": "It's pretty sad that UxU didn't get the success it deserved. I hope that it can have the ending the author planned instead of being forced to end like Bleach",
      "Link": "https://www.reddit.com/r/UndeadUnluck/comments/r81z7l/undead_unluck_has_been_recommended_by_tsukihime/hn2u44i/",
      "Time": "2021-12-03 15:45:14",
      "Percentage": 24.2
    },
    {
      "Pain Point": "Concern About Anime Adaptation's Reception",
      "Description": "Fans express anxiety over the anime adaptation potentially facing the same lack of understanding and appreciation as the manga, leading to criticism and jeopardizing its chances for a continuation.",
      "Quote": "I'm worried that no one will understand it and will even try to get it cancelled. I know I sound like a crybaby right now who cant handle the prices of media he likes getting criticized, but when that same criticism is so bad that you're not certain that the anime you've been waiting for about 2 years now to get animated might not even get a second season because of how the community took it, it's got to be crossing some kind of line.",
      "Link": "https://www.reddit.com/r/UndeadUnluck/comments/105f47c/im_worried_about_the_undead_unluck_anime/",
      "Time": "2023-01-07 03:58:44",
      "Percentage": 8.28
    },
    {
      "Pain Point": "Uncertainty About the Series' Future",
      "Description": "The announcement of Undead Unluck entering its 'final stages' sparks fear among fans that the series might face a premature or rushed ending due to its current popularity struggles.",
      "Quote": "It's pretty sad that UxU didn't get the success it deserved. I hope that it can have the ending the author planned instead of being forced to end like Bleach",
      "Link": "https://www.reddit.com/r/UndeadUnluck/comments/r81z7l/undead_unluck_has_been_recommended_by_tsukihime/hn2u44i/",
      "Time": "2021-12-03 15:45:14",
      "Percentage": 17.52
    },
    {
      "Pain Point": "Limited Accessibility for International Fans",
      "Description": "The lack of readily available fan translations and early leaks hinders international fans from accessing and engaging with the series promptly, putting them at a disadvantage compared to Japanese readers.",
      "Quote": "I was always wondering and have tried googling to see if the same happens for Undead Unluck but can't find anything.",
      "Link": "https://www.reddit.com/r/UndeadUnluck/comments/128wg86/undead_unluck_really_is_underrated_in_the_west/jelbfkx/",
      "Time": "2023-04-01 22:33:22",
      "Percentage": 10.19
    },
    {
      "Pain Point": "Inconsistent Release Schedule",
      "Description": "The irregular release pattern of the manga chapters poses a challenge for readers who prefer a more predictable and consistent schedule, making it difficult to maintain a steady engagement with the story.",
      "Quote": "I'm in love with it and will have a great next week watching it (I don't binge watch).",
      "Link": "https://www.reddit.com/r/UndeadUnluck/comments/1b96iwt/just_got_into_undead_unfuck_and_man_it_sure_is/",
      "Time": "2024-03-07 21:50:33",
      "Percentage": 4.46
    },
    {
      "Pain Point": "Difficulty Attracting New Readers",
      "Description": "Undead Unluck faces an uphill battle in captivating new readers due to its niche appeal and the initial hurdles presented by the early chapters, hindering its ability to expand its fanbase.",
      "Quote": "Yeah, UU is the kind of show you stumble upon by chance and goes like \"huh\". Very few people will sign Hulu specifically to watch it, specially when Hulu isn't even known for its anime.",
      "Link": "https://www.reddit.com/r/UndeadUnluck/comments/17xang1/thoughts/k9n4fzv/",
      "Time": "2023-11-17 14:51:54",
      "Percentage": 10.19
    },
    {
      "Pain Point": "Early Tone and Narrative Issues",
      "Description": "The manga's early chapters, particularly the first few arcs, draw criticism for their off-putting tone, unrealized ideas, and shifts in narrative, creating a barrier to entry for potential readers.",
      "Quote": "sadly the first few chapters kinda turned the west off of the manga. although they quickly get rid of that type of tone for the rest of the story the first impression stuck sadly :( hopefully the anime can bring people to U×U",
      "Link": "https://www.reddit.com/r/UndeadUnluck/comments/10cp6dl/how_is_this_manga_so_slept_on/j4hsjxn/",
      "Time": "2023-01-15 20:44:01",
      "Percentage": 25.16
    }
  ],
  "Personas": [
    {
      "persona_title": "The Intrigued Newcomer",
      "persona_reasoning": "This quote shows a new reader who is enjoying the manga and is interested in collecting more volumes.",
      "description": "New readers who are just starting to explore the Undead Unluck manga. They are drawn in by the unique concept, characters, and abilities. They are eager to learn more about the story and the world.",
      "quote": "I’ve been reading Undead Unluck and it’s definitely one of my favorite mangas. I really love the concept, the story and the characters with their negator abilities. So far I’m on chapter 5 and I’m been planning on reading the other volumes once I’m finished with volume 5.",
      "link": "https://www.reddit.com/r/UndeadUnluck/comments/1aol62c/heres_my_volume_collection_of_undead_unluck_so_far/",
      "latest_quote_time": "2024-02-11",
      "top_pain_points": [
        {
          "pain_point_title": "Initial Roughness",
          "pain_point_reasoning": "This quote highlights the common sentiment that the early chapters of the manga are rough and can be a turn-off for new readers.",
          "pain_point_description": "The first few chapters of Undead Unluck can be perceived as rough, potentially due to the initial fanservice elements and the unconventional introduction of the story and characters.",
          "pain_point_quote": "Terrible first chapters, even if it’s kino afterwards it is a really rough set of chapters lmao",
          "pain_point_link": "https://www.reddit.com/r/UndeadUnluck/comments/18z8kxr/why_isnt_undead_unluck_more_popular/kghafnz/"
        }
      ],
      "Percentage": 7.25
    },
    {
      "persona_title": "The Anime-First Fan",
      "persona_reasoning": "This quote represents a reader who started with the anime and then transitioned to the manga.",
      "description": "Fans who were introduced to Undead Unluck through the anime adaptation. They are drawn in by the animation, characters, and story. They are eager to explore the manga to see where the story goes beyond the anime.",
      "quote": "I read about 1/2 into the manga because I enjoyed the anime when it first aired. Thought the power system and rules were cool as well. Without spoiling too much though, I clocked out 1/2 into the manga. It was a bit too cringey with the relationships. I support healthy anime relationships and but this was just too much, at least for me. Also I’m not sure what the point of the manga is (unless they explain it in the chapters I missed). I understand it’s to kill undead, but I don’t see that happening either based on the few spoilers I’ve read",
      "link": "https://www.reddit.com/r/UndeadUnluck/comments/18z8kxr/why_isnt_undead_unluck_more_popular/kgohqe2/",
      "latest_quote_time": "2024-01-07",
      "top_pain_points": [
        {
          "pain_point_title": "Relationship Dynamics",
          "pain_point_reasoning": "The quote expresses discomfort with the portrayal of relationships in the manga, finding them cringey.",
          "pain_point_description": "Some readers find the relationship dynamics in the manga to be cringeworthy or uncomfortable, especially in the earlier chapters.",
          "pain_point_quote": "It was a bit too cringey with the relationships. I support healthy anime relationships and but this was just too much, at least for me.",
          "pain_point_link": "https://www.reddit.com/r/UndeadUnluck/comments/18z8kxr/why_isnt_undead_unluck_more_popular/kgohqe2/"
        }
      ],
      "Percentage": 11.23
    },
    {
      "persona_title": "The Dedicated Manga Reader",
      "persona_reasoning": "This quote highlights a reader who has been following the manga for a long time and considers it one of their favorites.",
      "description": "Experienced manga readers who have been following Undead Unluck for a significant duration. They appreciate the intricate world-building, complex characters, and strategic battles. They are highly invested in the story's progression and the fate of the characters.",
      "quote": "Just cought up with undead unluck. Had a 3-4 days binge read. This is the only other manga where The fondness I have for these characters almost hits the same highs for me as One Piece. The author, tozuka, is really good at utilizing his cast and might be my fav part of the series",
      "link": "https://www.reddit.com/r/UndeadUnluck/comments/1cm9tdo/undead_unluck_cast_of_characters/",
      "latest_quote_time": "2024-05-07",
      "top_pain_points": [
        {
          "pain_point_title": "Lack of Popularity",
          "pain_point_reasoning": "The quote expresses surprise and confusion as to why the manga isn't more widely recognized and appreciated.",
          "pain_point_description": "Dedicated fans of Undead Unluck are often perplexed by the manga's relative lack of popularity, considering its high quality and engaging story.",
          "pain_point_quote": "I’ve been wondering, why isn’t Undead Unluck more known? I’m not referring to the anime getting shafted to Hulu, although that didn’t do anything for it’s numbers, I’m referring to why Undead Unluck isn’t more popular as a manga. Undead Unluck is an amazing manga, and I’m surprised that it doesn’t get more recognition.",
          "pain_point_link": "https://www.reddit.com/r/UndeadUnluck/comments/18z8kxr/why_isnt_undead_unluck_more_popular/"
        }
      ],
      "Percentage": 48.19
    },
    {
      "persona_title": "The Lore Enthusiast",
      "persona_reasoning": "This quote reveals a reader who is deeply interested in the lore and world-building aspects of the manga.",
      "description": "Readers who are fascinated by the lore, rules, and intricacies of the Undead Unluck universe. They enjoy analyzing the power system, understanding the mechanics of negator abilities, and exploring the history and mythology of the world.",
      "quote": "I think a first 10 years of fuuko's loop would be interesting, seeing her grew into what she is now, tackling new umas as she finds the means to build the union and researching them",
      "link": "https://www.reddit.com/r/UndeadUnluck/comments/1cmrv18/what_should_an_undead_unluck_anime_movie_be_like/l33ax3d/",
      "latest_quote_time": "2024-05-08",
      "top_pain_points": [
        {
          "pain_point_title": "Limited Backstory Exploration",
          "pain_point_reasoning": "This quote highlights a desire for more in-depth exploration of certain backstories and events within the manga's history.",
          "pain_point_description": "Lore enthusiasts crave more detailed backstories and explanations of significant events that have shaped the Undead Unluck world.",
          "pain_point_quote": "I think a first 10 years of fuuko's loop would be interesting, seeing her grew into what she is now, tackling new umas as she finds the means to build the union and researching them",
          "pain_point_link": "https://www.reddit.com/r/UndeadUnluck/comments/1cmrv18/what_should_an_undead_unluck_anime_movie_be_like/l33ax3d/"
        }
      ],
      "Percentage": 24.82
    },
    {
      "persona_title": "The Crossover Fan",
      "persona_reasoning": "This quote shows a user who is specifically interested in crossover content related to Undead Unluck.",
      "description": "Fans who enjoy imagining Undead Unluck characters interacting with characters from other manga or anime series. They are drawn to the creative possibilities and potential for unique matchups and story ideas.",
      "quote": "I think soul eater would be a good one",
      "link": "https://www.reddit.com/r/UndeadUnluck/comments/1af60oq/what_is_your_idea_for_undead_unluck_crossover/kpph2qa/",
      "latest_quote_time": "2024-02-09",
      "top_pain_points": [
        {
          "pain_point_title": "Limited Crossover Content",
          "pain_point_reasoning": "This quote expresses a desire for more crossover content featuring Undead Unluck characters interacting with characters from other series.",
          "pain_point_description": "Crossover fans yearn for more fanfiction, fanart, and discussions exploring the potential for Undead Unluck crossovers with other popular manga or anime.",
          "pain_point_quote": "That is the Question Folks \n\nWhat is Your Idea for crossover fanfiction between Undead Unluck and Another Manga/Anime or Whatever and who would appear and where in Manga/Anime timeline would it be set in? Would it be prequel to the Series or set between Arcs or something like that?  How long would the crossover be and what fun interactions would there be?",
          "pain_point_link": "https://www.reddit.com/r/UndeadUnluck/comments/1af60oq/what_is_your_idea_for_undead_unluck_crossover/"
        }
      ],
      "Percentage": 8.51
    }
  ]
}