# jobtastic- Celery tasks plus more awesome

Jobtastic is a [Celery](http://celeryproject.org) library
that makes your user-responsive long-running jobs
totally awesomer.
Celery is the ubiquitous python job queueing tool
and jobtastic is a python library
that adds useful features to your Celery tasks.
Specifically, these are features you probably want
if the results of your jobs are expensive
or if your users need to wait while they compute their results.

Jobtastic gives you goodies like:
* Easy progress estimation/reporting
* Job status feedback
* Helper methods for gracefully handling a dead task broker
  (`delay_or_run` and `delay_or_fail`)
* A [celery jQuery plugin](https://github.com/PolicyStat/jquery-celery)
  for easy client-side progress display
* Result caching
* [Thundering herd](http://en.wikipedia.org/wiki/Thundering_herd_problem) avoidance

Make your Celery jobs more awesome with Jobtastic.

## Why Jobtastic?

If you have user-facing tasks for which a user must wait,
you should try Jobtastic.
It's great for:
* Complex reports
* Graph generation
* CSV exports
* Any long-running, user-facing job

You could write all of the stuff yourself, but why?

## Installation

1. Get the project source and install it

    $ pip install jobtastic

## Creating Your First Task

Let's take a look at an example task using Jobtastic:

	from jobtastic.task import JobtasticTask

	class LotsOfDivisionTask(JobtasticTask):
		"""
		Division is hard. Make Celery do it a bunch.
		"""
		# Any unique string works here
		cache_prefix = 'myapp.tasks.LotsOfDivisionTask'
		# These are the Task kwargs that matter for caching purposes
		significant_kwargs = [
			('numerators', str),
			('denominator', str),
		]
		# How long should we give a task before assuming it has failed?
		herf_avoidance_timeout = 20  # Shouldn't take more than 20 seconds
		# How long we want to cache results with identical ``significant_kwargs``
		cache_duration = 0  # Cache these results forever. Math is pretty stable.

		def calculate_result(self, numerators, denominators, **kwargs):
			"""
			MATH!!!
			"""
			results = []
			divisions_to_do = len(numerators)
			for count, divisors in enumerate(zip(numerators, denominators)):
				numerator, denominator = divisors
				results.append(numerator / denominator)
				# Let's let everyone know how we're doing
				self.update_progress(count, divisions_to_do)

			return results

This task is very trivial, but imagine doing something time-consuming instead
of division (or just a ton of division) while a user waited. We wouldn't want
a double-clicker to cause this to happen twice concurrently, we wouldn't want
to ever redo this work on the same numbers and we would want the user to have
at least some idea of how long they'll need to wait. Just by setting those 4
member variables, we've done all of these things.

Basically, creating a Celery task using Jobtastic is a matter of:

1. Subclassing `jobtastic.task.JobtasticTask`
2. Defining some required member variables
3. Writing your `calculate_result` method
  (instead of the normal Celery `run()` method)
4. Sprinkling `update_progress()` calls in your `calculate_result()` method
  to communicate progress

### Required Member Variables

"But wait, Wes. What the heck do those member variables actually do?" You ask.

Firstly. How the heck did you know my name?
And B, why don't I tell you!

#### cache_prefix

#### significant_kwargs

#### herd_avoidance_timeout

#### cache_duration

### calculate_result

### update_progress

## Using your JobtasticTask

### delay_or_run

### delay_or_fail

## Client Side Handling

That's all well and good on the server side,
but the biggest benefit of Jobtastic is useful user-facing feedback.
That means handling status checks using AJAX in the browser.

The easiest way to get rolling is to use our sister project,
[jquery-celery](https://github.com/PolicyStat/jquery-celery).
It contains jQuery plugins that help you:
* Poll for task status and handle the result
* Display a progress bar using the info from the `PROGRESS` state.
* Display tabular data using [DataTables](http://www.datatables.net/).

If you want to roll your own,
the general pattern is to poll a URL
(such as the django-celery
[task_status view](https://github.com/celery/django-celery/blob/master/djcelery/urls.py#L25) )
with your taskid to get JSON status information
and then handle the possible states to keep the user informed.

The [jquery-celery](https://github.com/PolicyStat/jquery-celery/blob/master/src/celery.js)
jQuery plugin might still be useful as reference,
even if you're rolling your own.
In general, you'll want to handle the following cases:

### PENDING

Your task is still waiting for a worker process.
It's generally useful to display something like "Waiting for your task to begin".

### PROGRESS

Your task has started and you've got a JSON object like:

    {
        "progress_percent": 0,
        "time_remaining": 300
    }

`progress_percent` is a number between 0 and 100.
It's a good idea to give a different message if the percent is 0,
because the time remaining estimate might not yet be well-calibrated.

`time_remaining` is the number of seconds estimated to be left.
If there's no good estimate available, this value will be `-1`.

### SUCCESS

You've got your data. It's time to display the result.

### FAILURE

Something went wrong and the worker reported a failure.
This is a good time to either display a useful error message
(if the user can be expected to correct the problem),
or to ask the user to retry their task.

### Non-200 Request

There are occasions where requesting the task status itself might error out.
This isn't a reflection on the worker itself,
as it could be caused by any number of application errors.
In general, you probably want to try again if this happens,
but if it persists, you'll want to give your user feedback.

## Is it Awesome?

Yes. Increasingly so.

# Non-affiliation

This project isn't affiliated with the awesome folks at the
[Celery Project](http://www.celeryproject.org)
(unless having a huge crush counts as affiliation).
It's a library that the folks at [PolicyStat](http://www.policystat.com)
have been using internally and decided to open source in the hopes it is useful to others.
