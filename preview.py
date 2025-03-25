import ffmpeg

# Calculate sample_seconds based on the video duration, sample_duration and number of samples
def calculate_sample_seconds(duration, samples, sample_duration):
    sample_seconds = []
    sample_spacing = duration / samples

    # Sample spacing must always be larger than sample length
    if sample_spacing < sample_duration:
        raise Exception('sample_duration should be shorter then: {}'.format(sample_spacing))

    for i in range(samples):
        sample_seconds.append(sample_spacing * i)

    return sample_seconds

def sample_video(in_file, sample_duration, sample_seconds=[]):
    samples = []
    for t in sample_seconds:
        stream = in_file.video.trim(start=t, duration=sample_duration).setpts('PTS-STARTPTS')
        samples.append(stream)
    return samples

def generate_video_preview(in_filename, out_filename, sample_duration, sample_seconds, scale, format, quiet):
    in_file = ffmpeg.input(in_filename)

    samples = sample_video(in_file, sample_duration=sample_duration, sample_seconds=sample_seconds)
    stream = ffmpeg.concat(*samples)

    if scale is not None:
        width, height = scale.split(':')
        stream = ffmpeg.filter(stream, 'scale', width=width, height=height, force_original_aspect_ratio='decrease')

    (
        ffmpeg
        .output(stream, out_filename, format=format)
        .overwrite_output()
        .run(quiet=quiet)
    )