
# Welcome to Sherlock

SherlockHolmie is a data analytics and research platform that analyzes Reddit content to generate insights for
businesses or researchers. The system:

1. Data Collection: Downloads and processes Reddit posts/comments from specified subreddits using the Reddit API.
2. Data Processing:
  - Stores content in PostgreSQL databases
  - Creates vector embeddings for semantic search
  - Uses LLMs (Claude, GPT-4, Gemini) to extract insights
3. Research Generation:
  - Identifies pain points in communities
  - Creates user personas
  - Extracts behavioral and attitudinal insights
  - Supports specific queries about topics
4. Frontend Interface:
  - Modern Next.js application
  - Chat interface for interacting with insights
  - Report viewing and generation capabilities
  - Authentication and user management
5. Cloud Infrastructure:
  - Uses AWS CDK for infrastructure as code
  - Includes AWS resources like:
      - Lambda functions
    - ECS clusters
    - RDS databases
    - VPC configuration
    - EC2 instances
6. Deployment:
  - Docker containers for services
  - Celery for task processing
  - Various deployment scripts

Important Folders 
- /cdk_stacks -  Important to deploy Code to AWS
    - CDK Stacks
    - Cluster Stack - Code for deploying subreddit downloader Fargate task to aws
    - VPC Stack - Code for deploying VPC
    - Lambda Stack - Code for deploying AWS Lambda Endpoint for public use.
    - Database Stack - Code for deploying Datatabase
-/Lambda - Code for AWS Lambda task to start subreddit downloader
-/Backend
    - Report generation, ETL, and managers

## Useful commands

 * `cdk deploy` - Deploy stack to AWS
 * `tasks/deploy.sh` - Deploy task services

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

## POST `/process_query`

This endpoint processes a given query and space and returns the relevant insights.

### Request Body

The request body should be a JSON object with the following properties:

- `space` (string, required): The space to process.
- `query` (string, required): The query to process.

Additonal parameters:

- `fast` (bool,optional) : Controls whether the database uses the index or not - Default:True
- `threshold`(bool,optional): Controls how many posts are analyzed Default: 0.55

### Response

The response is a JSON object with the following properties:

- `Initialization Time` (number): The time taken to initialize the space.
- `researchInsights` (object): An object containing the insights for this query.

### Example

Request:

```json
{
    "space": "Discussions about Cash Advance and Credit Earning",
    "query" :"How long are people using cash advance type apps for?",
    "fast": false,
    "threshold":0.55
}

{
  "Initialization Time": 359.93976855278015,
  "Insights": {
    "researchInsights": {
      "attitudinal": [
        {
          "insight": "People use cash advance apps for short-term financial needs.",
          "source": "https://www.reddit.com/r/povertyfinance/comments/14n6z2p/cash_advance_apps_for_those_who_get_declined_from/k0vamxn/",
          "quote": "Cash advance apps can be an option for individuals who have been declined by traditional lenders or face difficulties accessing credit through conventional means.",
          "date": "2023-09-14T23:33:11Z"
        },
        {
          "insight": "People use cash advance apps to avoid overdraft fees.",
          "source": "https://www.reddit.com/r/povertyfinance/comments/172z8r9/is_it_possible_to_obtain_a_loan_or_cash_advance/k40ujs5/",
          "quote": "I used them to avoid overdraft fees, because the fees/tips from these apps was less than getting hit with late fees and/or overdraft fees of $34/transaction, max like $102 a day.",
          "date": "2023-10-08T18:33:00Z"
        },
        {
          "insight": "People use cash advance apps to avoid the hassle of traditional lenders.",
          "source": "https://www.reddit.com/r/povertyfinance/comments/14myzlj/100_short_on_rent/jq6tfnz/",
          "quote": "I don’t really consider these as bad as “cash advance” places that charge ridiculous interest. I may be wrong.",
          "date": "2023-06-30T22:12:04Z"
        },
        {
          "insight": "People use cash advance apps because of their speed and reliability.",
          "source": "https://www.reddit.com/r/poor/comments/19fav29/what_ever_happened_to_the_places_that_look_at/kjkr3to/",
          "quote": "I’ve been fortunate to use NetPayAdvance when I’ve needed a bigger amount. I usually get the loan for $255 and they are super fast and reliable. Best of all they don’t bug haha. I’ve never been denied from them- especially when I’d been denied other places.",
          "date": "2024-01-25T23:05:29Z"
        },
        {
          "insight": "People are concerned about getting stuck in a cycle of debt with cash advance apps.",
          "source": "https://www.reddit.com/r/povertyfinance/comments/1b3wvre/please_guys_never_use_cash_advance_apps_if_you/",
          "quote": "You will get trapped in a borrowing loop BAD. I never thought it would happen to me but one day i needed 50$ i had no money and found Earnin. Thought awesome this is cool ! Borrow 2 weeks early no problem !",
          "date": "2024-03-01T15:24:13Z"
        },
        {
          "insight": "People are concerned about the high fees and interest rates associated with cash advance apps.",
          "source": "https://www.reddit.com/r/Money/comments/t4hmb9/possible_loan_app/iepcci8/",
          "quote": "If you are in need and don't want to go through the process in person, it's useful in down situations. I'd consider all options before doing it. I like it because you can pay back in installments, for example say you are approved for $200 and you have to pay back $250 over the course of 4 payments, 1 payment every 2 weeks. Rather than the other payday loan apps that charge all of the loan on payday.",
          "date": "2022-07-03T15:02:13Z"
        },
        {
          "insight": "People use cash advance apps because they are seen as a more consumer-friendly alternative to payday loans.",
          "source": "https://www.reddit.com/r/povertyfinance/comments/172z8r9/is_it_possible_to_obtain_a_loan_or_cash_advance/k40o63m/",
          "quote": "The newer 'cash advance apps' are more consumer friendly (less unfriendly?) than payday loans. You can actually borrow from some of these apps with no interest or fees if you're willing to jump through a few hoops.",
          "date": "2023-10-08T17:56:07Z"
        },
        {
          "insight": "People are concerned about the impact of cash advance apps on their credit score.",
          "source": "https://www.reddit.com/r/Money/comments/124kq30/i_need_to_make_some_money_and_i_need_to_make_it/je0mkw8/",
          "quote": "I might need to use this. Do they affect credit in any way?",
          "date": "2023-03-28T15:42:50Z"
        },
        {
          "insight": "People are looking for ways to break free from the cycle of using cash advance apps.",
          "source": "https://www.reddit.com/r/Earnin/comments/18yseqp/need_advice/",
          "quote": "Has anybody on here been able to break free from the cycle of using payday loan apps. I’ve never been good with saving and one emergency had cause me to delve into not only earnin, but a lot of the other mobile apps. how did you guys break that cycle? i’m trying my best to tackle this before january is over.",
          "date": "2024-01-05T00:08:03Z"
        }
      ],
      "behavioral": [
        {
          "insight": "People use multiple cash advance apps at the same time.",
          "source": "https://www.reddit.com/r/povertyfinance/comments/1bkbyij/any_advice_yall_cash_advance_apps/",
          "quote": "I use Earnin, Dave, Moneylion and Empower. Any advice would help me y’all, thank you guys!!",
          "date": "2024-03-21T17:21:29Z"
        },
        {
          "insight": "People use cash advance apps for multiple years.",
          "source": "https://www.reddit.com/r/Earnin/comments/16qk297/b4b_quick_response/k21s1lt/",
          "quote": "I've used Dave app for advances for about 4 years now they used to offer a hell of a lot more than what they do now as far as the frequency of offers.",
          "date": "2023-09-24T21:13:32Z"
        },
        {
          "insight": "People use cash advance apps regularly, often every pay cycle.",
          "source": "https://www.reddit.com/r/chimefinancial/comments/1cq2oy5/cash_advance_help/l3rr7cj/",
          "quote": "But I used to use them every pay cycle to help the amount allowed to borrow grow.",
          "date": "2024-05-12T22:21:09Z"
        },
        {
          "insight": "People use cash advance apps to build up their borrowing limit.",
          "source": "https://www.reddit.com/r/VaroMoney/comments/1as7azc/advance/kqpyyb5/",
          "quote": "Ever since I got the app and got the required direct deposit they started me at 20 and over the span of couple months I got to over 200.",
          "date": "2024-02-16T18:23:56Z"
        },
        {
          "insight": "People use cash advance apps in a pinch, when they need money immediately.",
          "source": "https://www.reddit.com/r/povertyfinance/comments/172z8r9/is_it_possible_to_obtain_a_loan_or_cash_advance/k3zpiig/",
          "quote": "Ugh, loans and cash advances are such a pain. But yeah, you can probably get $300 pretty quick if you're desperate enough.",
          "date": "2023-10-08T14:24:03Z"
        },
        {
          "insight": "People use cash advance apps to avoid having to rely on payday loans.",
          "source": "https://www.reddit.com/r/Money/comments/t4hmb9/possible_loan_app/iepcci8/",
          "quote": "If you are in need and don't want to go through the process in person, it's useful in down situations. I'd consider all options before doing it. I like it because you can pay back in installments, for example say you are approved for $200 and you have to pay back $250 over the course of 4 payments, 1 payment every 2 weeks. Rather than the other payday loan apps that charge all of the loan on payday.",
          "date": "2022-07-03T15:02:13Z"
        },
        {
          "insight": "People use cash advance apps to help them budget.",
          "source": "https://www.reddit.com/r/povertyfinance/comments/172z8r9/is_it_possible_to_obtain_a_loan_or_cash_advance/k40ujs5/",
          "quote": "It’s useful, but always plan your finances to avoid depending on these advances.",
          "date": "2024-04-17T12:47:37Z"
        },
        {
          "insight": "People use cash advance apps because they are easy to use.",
          "source": "https://www.reddit.com/r/povertyfinance/comments/vcj0cq/is_there_any_way_to_get_a_500_cash_advance_or/kzz99tw/",
          "quote": "I’ve been using Fund Finance occasionally when the end of the month gets tough. The application is straightforward and approval is quick.",
          "date": "2024-04-17T12:47:37Z"
        },
        {
          "insight": "People use cash advance apps for a variety of reasons, including emergencies, budgeting, and avoiding overdraft fees.",
          "source": "https://www.reddit.com/r/povertyfinance/comments/172z8r9/is_it_possible_to_obtain_a_loan_or_cash_advance/k40ujs5/",
          "quote": "Those are the only ones I’ve used regularly. I’ve heard of others but they were either too small of an amount (like $60) or tied to an organization or something.",
          "date": "2023-10-08T18:33:00Z"
        },
        {
          "insight": "People use cash advance apps as a last resort.",
          "source": "https://www.reddit.com/r/povertyfinance/comments/14n6z2p/cash_advance_apps_for_those_who_get_declined_from/k0mhik6/",
          "quote": "However, it's essential to be aware that these loans often come with high fees and interest rates, so they should be used as a last resort.",
          "date": "2023-09-14T23:33:11Z"
        }
      ]
    },
    "conclusion": "Based on the attitudinal and behavioral research insights, it is clear that people use cash advance apps primarily for short-term financial needs, such as covering unexpected expenses, avoiding overdraft fees, and bridging the gap between paychecks. Users often rely on these apps for their speed, reliability, and ease of use. However, there are significant concerns about the high fees, potential for getting stuck in a cycle of debt, and the impact on credit scores. While some users have been using these apps for multiple years, others use them regularly, often every pay cycle, and sometimes multiple apps simultaneously. Overall, cash advance apps are seen as a last resort and a temporary solution rather than a long-term financial strategy.",
    "userSegments": [
      {
        "segment": "Short-term Financial Needers",
        "description": "Users who rely on cash advance apps to cover immediate expenses and bridge the gap between paychecks."
      },
      {
        "segment": "Overdraft Avoiders",
        "description": "Users who use cash advance apps to avoid overdraft fees and manage their finances more effectively."
      },
      {
        "segment": "Emergency Fund Seekers",
        "description": "Users who turn to cash advance apps in times of financial emergencies, such as unexpected expenses or urgent bills."
      },
      {
        "segment": "Cycle of Debt Concerned",
        "description": "Users who are aware of the potential risks of getting stuck in a cycle of debt and are looking for ways to break free from it."
      }
    ]
  }
}